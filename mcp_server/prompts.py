from mcp_server.app import mcp
from fastmcp import Message, UserMessage, AssistantMessage

@mcp.prompt()
def draft_passenger_delay_email(
    passenger_name: str, 
    flight_number: str, 
    delay_minutes: int,
    reason: str = "operational delay"
) -> list[Message]:
    """Generates a structured prompt template for drafting passenger disruption emails."""
    
    system_instruction = (
        "You are an empathetic customer service assistant for EgyptAir. "
        "Your task is to draft a professional, polite apology email to a passenger "
        "whose flight has been disrupted."
    )
    
    user_request = (
        f"Draft a formal apology email to {passenger_name}.\n"
        f"Flight Details:\n"
        f"- Flight Number: {flight_number}\n"
        f"- Delay Duration: {delay_minutes} minutes\n"
        f"- Reason: {reason}\n\n"
        f"Include information on next steps and express gratitude for their patience."
    )
    try:
        return [
        UserMessage(content=f"[SYSTEM INSTRUCTION]: {system_instruction}\n\n{user_request}")
    ]
    except Exception as e:
        return (
            f"Raw Error: {str(e)}"
        )
