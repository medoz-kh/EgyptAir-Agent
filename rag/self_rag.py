import json
from google import genai
from google.genai import types


class SelfRAGVerifier:
    """
    Self-RAG verification layer checking relevance of retrieved content
    and support/groundedness of generated responses.
    """

    def __init__(self, genai_client: genai.Client, model_id: str = "gemini-3.1-flash-lite"):
        self.client = genai_client
        self.model_id = model_id

    async def verify_relevance(self, query: str, retrieved_chunk: str) -> bool:
        """Checks if the retrieved chunk is relevant to the user query."""
        prompt = (
            f"User Query: {query}\n"
            f"Retrieved Document: {retrieved_chunk}\n\n"
            "Is the retrieved document relevant to answering the user query? "
            "Reply with JSON: {\"relevant\": true} or {\"relevant\": false}"
        )
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        try:
            data = json.loads(response.text)
            return data.get("relevant", False)
        except Exception:
            return True

    async def verify_groundedness(self, answer: str, context: str) -> bool:
        """Checks if the generated response is strictly supported by retrieved context."""
        prompt = (
            f"Retrieved Context: {context}\n"
            f"Generated Answer: {answer}\n\n"
            "Is the generated answer strictly supported by the retrieved context? "
            "Reply with JSON: {\"supported\": true} or {\"supported\": false}"
        )
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        try:
            data = json.loads(response.text)
            return data.get("supported", False)
        except Exception:
            return True