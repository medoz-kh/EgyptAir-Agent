import json
from dataclasses import dataclass
from google import genai
from google.genai import types
import inspect


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


# ==============================================================================
# OPTION B: GROUNDING CHECK ADD-ON (DRAFT -> CRITIQUE -> RETRY)
# ==============================================================================

ANSWER_PROMPT = """\
Answer the question using ONLY the context chunks below. If the chunks
don't contain the answer, say so plainly instead of guessing.

Question: {query}

Context chunks:
{chunks}

Answer:
"""

CRITIQUE_PROMPT = """\
Question: {query}
Draft answer: {answer}
Context chunks used:
{chunks}

Is every claim in the draft answer directly supported by the context
chunks above? Reply with exactly one line:
PASS
or
FAIL: <short reason, and what a better search query would look like>
"""

@dataclass
class Draft:
    query: str
    answer: str
    chunks: list[str]

@dataclass
class Critique:
    passed: bool
    reason: str
    suggested_query: str | None

class GroundingGuardrail:
    """
    Implements Option B: Drafts an answer, critiques if it is grounded in the chunks,
    and retries exactly once if it fails.
    """
    def __init__(self, search_tool, genai_client: genai.Client, model_id: str = "gemini-3.1-flash-lite"):
        self.search_tool = search_tool
        self.client = genai_client
        self.model_id = model_id

    async def build_draft_answer(self, query: str, top_k: int = 3) -> Draft:
        # Await the search tool if it's async, otherwise run it normally
        if inspect.iscoroutinefunction(self.search_tool):
            hits = await self.search_tool(query, top_k)
        else:
            hits = self.search_tool(query, top_k)
            
        # Extract text chunks smoothly whether search returns tuples (text, score) or objects
        chunks = []
        for hit in hits:
            if isinstance(hit, tuple):
                chunks.append(hit[0])
            else:
                chunks.append(getattr(hit, 'page_content', str(hit)))

        formatted = "\n".join(f"- {c}" for c in chunks)
        
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=ANSWER_PROMPT.format(query=query, chunks=formatted)
        )
        return Draft(query=query, answer=response.text, chunks=chunks)

    async def critique_answer(self, draft: Draft) -> Critique:
        formatted_chunks = "\n".join(f"- {c}" for c in draft.chunks)
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=CRITIQUE_PROMPT.format(query=draft.query, answer=draft.answer, chunks=formatted_chunks)
        )
        verdict = response.text.strip()

        if verdict.upper().startswith("PASS"):
            return Critique(passed=True, reason="", suggested_query=None)

        reason = verdict.split(":", 1)[1].strip() if ":" in verdict else verdict
        return Critique(passed=False, reason=reason, suggested_query=None)

    async def answer_with_grounding_check(self, query: str, top_k: int = 3) -> str:
        draft = await self.build_draft_answer(query, top_k=top_k)
        critique = await self.critique_answer(draft)

        if critique.passed:
            return draft.answer

        # Exactly one retry utilizing the generated critique reason
        retry_query = f"{query} (be more specific: {critique.reason})"
        retry_draft = await self.build_draft_answer(retry_query, top_k=top_k)
        retry_critique = await self.critique_answer(retry_draft)

        if retry_critique.passed:
            return retry_draft.answer

        return "I couldn't find a grounded answer to this in the knowledge base."