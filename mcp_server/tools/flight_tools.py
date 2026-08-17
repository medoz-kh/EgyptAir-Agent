from mcp_server.database import get_connection
from mcp_server.app import mcp


@mcp.tool()
def get_flight_status(flight_number: str) -> dict:
    """
    Retrieve the current status and delay information for an EgyptAir flight.
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
            (flight_number,),
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