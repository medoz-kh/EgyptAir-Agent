from mcp_server.database import get_connection
from mcp_server.app import mcp
from mcp_server.authorization import authorize_manager, authorize_customer_service
from mcp_server.notifications import notify_tools_changed
from mcp_server.validation import (
    validate_booking_exists,
    validate_requested_amount,
    validate_flight_eligible_for_compensation,
)
from fastmcp import Context
from pydantic import BaseModel, Field, ConfigDict

# -----------------------------
# Strict JSON Schemas
# -----------------------------
class SubmitCompensationArgs(BaseModel):
    employee_id: int = Field(..., description="The ID of the employee submitting the request.")
    booking_id: int = Field(..., description="The ID of the booking.")
    requested_amount: float = Field(..., description="Amount requested.", gt=0)
    reason: str = Field(..., description="Reason for compensation.")
    
    # This enforces additionalProperties: false
    model_config = ConfigDict(extra="forbid")

class ApproveCompensationArgs(BaseModel):
    employee_id: int = Field(..., description="The ID of the manager.")
    request_id: int = Field(..., description="The ID of the compensation request.")
    
    model_config = ConfigDict(extra="forbid")

@mcp.tool()
def submit_compensation_request(args: SubmitCompensationArgs) -> dict:
    """
    Submit a new compensation request for a passenger.
    Only Customer Service employees are allowed to create requests.
    """
    auth = authorize_customer_service(args.employee_id)
    if not auth["authorized"]:
        return auth

    booking_validation = validate_booking_exists(args.booking_id)
    if not booking_validation["valid"]:
        return booking_validation

    amount_validation = validate_requested_amount(args.requested_amount)
    if not amount_validation["valid"]:
        return amount_validation

    eligibility_validation = validate_flight_eligible_for_compensation(args.booking_id)
    if not eligibility_validation["valid"]:
        return eligibility_validation

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO CompensationRequests
            (booking_id, requested_amount, reason, status, approved_by, created_at)
            VALUES (?, ?, ?, 'Pending', NULL, DATE('now'))
            """,
            (args.booking_id, args.requested_amount, args.reason),
        )
        connection.commit()
        request_id = cursor.lastrowid
        
        return {
            "success": True,
            "request_id": request_id,
            "booking_id": args.booking_id,
            "status": "Pending",
            "message": "Compensation request submitted successfully."
        }
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": f"Database error: {str(e)}"}
    finally:
        connection.close()


@mcp.tool()
async def approve_compensation(args: ApproveCompensationArgs, ctx: Context) -> dict:
    """
    Approve or reject a compensation request.
    Only managers can perform this action.
    """
    auth = authorize_manager(args.employee_id)
    if not auth["authorized"]:
        return auth

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT status, requested_amount, booking_id
            FROM CompensationRequests
            WHERE request_id = ?
            """,
            (args.request_id,)
        )
        request = cursor.fetchone()

        if request is None:
            return {"success": False, "message": "Compensation request not found."}

        # The handler logic is now fixed: it only elicits IF it is pending.
        if request["status"] != "Pending":  
            return {"success": False, "message": f"Request is already {request['status']}."}

        confirmation = await ctx.elicit(
            message=f"""
            Are you sure you want to approve this compensation request?
            Request ID: {args.request_id}
            Booking ID: {request["booking_id"]}
            Requested Amount: ${request["requested_amount"]}
            """,
            response_type=bool,
        )

        if confirmation.action != "accept":
            return {"success": False, "message": "Operation cancelled by user."}

        approve = confirmation.data
        new_status = "Approved" if approve else "Rejected"

        cursor.execute(
            """
            UPDATE CompensationRequests
            SET status = ?, approved_by = ?
            WHERE request_id = ?
            """,
            (new_status, args.employee_id, args.request_id),
        )
        connection.commit()
        
        # Emits the tool change notification safely
        await notify_tools_changed(ctx)

        return {
            "success": True,
            "request_id": args.request_id,
            "status": new_status,
            "approved_by": args.employee_id,
            "message": f"Request {new_status.lower()} successfully."
        }
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": f"Database error: {str(e)}"}
    finally:
        connection.close()