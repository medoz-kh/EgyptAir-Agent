from database import get_connection
from app import mcp
from pydantic import BaseModel, Field, ConfigDict

# -----------------------------
# Strict JSON Schema
# -----------------------------
class GetBookingDetailsArgs(BaseModel):
    booking_id: int = Field(..., description="The ID of the booking to retrieve.")
    
    # Enforces additionalProperties: false
    model_config = ConfigDict(extra="forbid")

@mcp.tool()
def get_booking_details(args: GetBookingDetailsArgs) -> dict:
    """
    Retrieve booking details including passenger and flight information.
    """
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                b.booking_id,
                p.full_name,
                p.passport_number,
                f.flight_number,
                f.origin,
                f.destination,
                b.seat_number,
                b.ticket_class,
                b.booking_status
            FROM Bookings b
            JOIN Passengers p
                ON b.passenger_id = p.passenger_id
            JOIN Flights f
                ON b.flight_id = f.flight_id
            WHERE b.booking_id = ?
            """,
            (args.booking_id,),
        )

        booking = cursor.fetchone()

        if booking is None:
            return {
                "found": False,
                "message": "Booking not found."
            }

        return {
            "found": True,
            "booking_id": booking["booking_id"],
            "passenger_name": booking["full_name"],
            "passport_number": booking["passport_number"],
            "flight_number": booking["flight_number"],
            "origin": booking["origin"],
            "destination": booking["destination"],
            "seat_number": booking["seat_number"],
            "ticket_class": booking["ticket_class"],
            "booking_status": booking["booking_status"],
        }
    except Exception as e:
        return {"found": False, "message": f"Database error: {str(e)}"}
    finally:
        connection.close()