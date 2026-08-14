from google import genai
from google.genai import types

async def plan_and_solve(question: str, client: genai.Client, model_id: str = "gemini-3.1-flash-lite") -> str:
    """
    Executes Plan-and-Solve prompting using the Gemini API.
    Clearly separates the PLAN from the SOLUTION.
    """
    system_instruction = "You use Plan-and-Solve prompting. Clearly separate PLAN from SOLUTION."
    
    prompt = (
        f"{question}\n\n"
        "First understand the problem and devise a plan to solve it. "
        "Then carry out the plan step by step. Check calculations and common-sense assumptions."
    )

    response = await client.aio.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        )
    )

    if not response.text or not response.text.strip():
        raise RuntimeError("The chat model returned an empty or unsupported response")
        
    return response.text.strip()