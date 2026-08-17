import json
from fastmcp import FastMCP, Context
from mcp_server.app import mcp
from mcp_server.database import get_connection

@mcp.tool()
async def draft_passenger_email(booking_id: int, ctx: Context) -> str:
    """
    Fetches passenger and flight disruption details for a given booking_id,
    then uses MCP Sampling (ctx.session.create_message) to request the client's
    LLM to generate a professional apology email.
    """
    # 1. Fetch relevant booking, passenger, and flight details safely from SQLite
    connection = get_connection()
    connection.row_factory = lambda cursor, row: {
        col[0]: row[idx] for idx, col in enumerate(cursor.description)
    }
    cursor = connection.cursor()

    cursor.execute("""
        SELECT 
            p.full_name, 
            f.flight_number, 
            f.status, 
            f.delay_minutes,
            f.origin,
            f.destination
        FROM Bookings b
        JOIN Passengers p ON b.passenger_id = p.passenger_id
        JOIN Flights f ON b.flight_id = f.flight_id
        WHERE b.booking_id = ?
    """, (booking_id,))

    booking_data = cursor.fetchone()
    connection.close()

    # 2. Server-side validation
    if not booking_data:
        return f"Error: Booking ID {booking_id} not found in database."

    # 3. Construct prompt context for the client LLM
    passenger_name = f"{booking_data['full_name']} "
    flight_number = booking_data['flight_number']
    status = booking_data['status']
    delay_minutes = booking_data['delay_minutes']
    origin = booking_data['origin']
    destination = booking_data['destination']

    prompt_content = (
        f"Draft a formal and empathetic customer service email from EgyptAir.\n\n"
        f"Passenger Details:\n"
        f"- Name: {passenger_name}\n"
        f"- Flight: {flight_number} ({origin} to {destination})\n"
        f"- Flight Status: {status}\n"
        f"- Delay Duration: {delay_minutes} minutes\n\n"
        f"Requirements:\n"
        f"- Express sincere apologies for the disruption.\n"
        f"- Reassure the passenger that EgyptAir staff are working to resolve the delay.\n"
        f"- Maintain a courteous and professional brand tone."
    )

    # 4. SAMPLING REQUEST: Server asks Client's LLM model to write the message
    try:
        sampling_response = await ctx.session.create_message(
            messages=[
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt_content
                    }
                }
            ],
            max_tokens=350,
            system_prompt="You are an automated communications assistant for EgyptAir customer service."
        )

        # 5. Extract text from the sampling response object
        generated_email = sampling_response.content.text
        return generated_email

    except Exception as e:
        # Fallback handling if client does not support or denies sampling capability
        return (
            f"[Sampling Error / Client Rejected Request]: Could not request model generation. "
            f"Details for manual processing -> Passenger: {passenger_name}, Flight: {flight_number}, Delay: {delay_minutes} mins. "
            f"Raw Error: {str(e)}"
        )