from database import get_connection
from app import mcp
from pydantic import BaseModel, Field, ConfigDict

# -----------------------------
# Strict JSON Schema
# -----------------------------
class GetFlightStatusArgs(BaseModel):
    flight_number: str = Field(..., description="The flight number to check.")
    
    # Enforces additionalProperties: false
    model_config = ConfigDict(extra="forbid")

@mcp.tool()
def get_flight_status(args: GetFlightStatusArgs) -> dict:
    """
    Retrieve the current status and schedule of a flight using its flight number.
    """
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                flight_number,
                origin,
                destination,
                departure_time,
                arrival_time,
                status,
                delay_minutes
            FROM Flights
            WHERE flight_number = ?
            """,
            (args.flight_number,),
        )

        flight = cursor.fetchone()

        if flight is None:
            return {
                "found": False,
                "message": "Flight not found."
            }

        return {
            "found": True,
            "flight_number": flight["flight_number"],
            "origin": flight["origin"],
            "destination": flight["destination"],
            "departure_time": flight["departure_time"],
            "arrival_time": flight["arrival_time"],
            "status": flight["status"],
            "delay_minutes": flight["delay_minutes"],
        }
    except Exception as e:
        return {"found": False, "message": f"Database error: {str(e)}"}
    finally:
        connection.close()