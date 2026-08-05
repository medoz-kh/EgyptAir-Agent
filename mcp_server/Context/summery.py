from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class ConversationSummarySchema(BaseModel):
    """Pydantic schema for structured memory compression."""
    high_level_summary: str = Field(description="A concise summary of the conversation so far.")
    user_intent: str = Field(description="The primary goal or active request of the user.")
    key_entities: List[str] = Field(default_factory=list, description="Flight numbers, names, or booking IDs.")
    unresolved_actions: List[str] = Field(default_factory=list, description="Pending tasks or parameters needed.")

class RecursiveSummarizationStrategy:
    """
    Strategy 3: Recursive Summarization
    Uses Gemini to compress older history into a structured Pydantic schema
    and prepends it as a single memory turn.
    """
    def __init__(self, window_size: int = 6):
        self.window_size = window_size
        self.running_summary: Optional[ConversationSummarySchema] = None

    async def process(
        self, 
        history: List[types.Content], 
        genai_client: Optional[genai.Client] = None, 
        model_id: str = "gemini-2.5-flash"
    ) -> List[types.Content]:
        if len(history) < self.window_size or not genai_client:
            return history

        items_to_summarize = history[:-4]
        recent_items = history[-4:]

        # Format transcript text
        transcript = ""
        for msg in items_to_summarize:
            role = msg.role
            for p in msg.parts:
                if hasattr(p, "text") and p.text:
                    transcript += f"{role}: {p.text}\n"

        try:
            summary_prompt = f"Summarize this conversation transcript into structured memory:\n\n{transcript}"
            
            response = await genai_client.aio.models.generate_content(
                model=model_id,
                contents=summary_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ConversationSummarySchema
                )
            )

            summary_obj = ConversationSummarySchema.model_validate_json(response.text)
            self.running_summary = summary_obj

            summary_text = (
                f"[STRUCTURED MEMORY SUMMARY]\n"
                f"Summary: {summary_obj.high_level_summary}\n"
                f"User Intent: {summary_obj.user_intent}\n"
                f"Entities: {', '.join(summary_obj.key_entities)}\n"
                f"Pending: {', '.join(summary_obj.unresolved_actions)}"
            )

            compressed_history = [
                types.Content(role="user", parts=[types.Part.from_text(text=summary_text)])
            ]
            compressed_history.extend(recent_items)
            return compressed_history

        except Exception as e:
            print(f"⚠️ Summarization failed ({e}), falling back to standard history.")
            return history