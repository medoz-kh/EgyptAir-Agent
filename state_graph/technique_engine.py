"""
technique_engine.py -- GeminiTechniqueEngine.

All Gemini API calls live here and nowhere else in state_graph/. Nodes call
`deps.technique.<method>`; they never import google.genai. This mirrors the
existing pattern in rag/self_rag.py (structured JSON output via
response_mime_type="application/json") so it stays consistent with code
already in the repo rather than inventing a new calling convention.

Important: this engine PROVIDES reasoning/planning decisions requested by
nodes. It does not decide what happens next in the workflow -- routers.py
does that, deterministically, from AgentState. See project brief section 11.
"""

from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import types

DEFAULT_MODEL_ID = "gemini-3.1-flash-lite"


class GeminiTechniqueEngine:
    """Real Gemini-backed implementation of the TechniqueEngine protocol."""

    def __init__(self, genai_client: genai.Client, model_id: str = DEFAULT_MODEL_ID):
        self.client = genai_client
        self.model_id = model_id

    async def _json_call(self, prompt: str, system_instruction: str | None = None) -> dict[str, Any]:
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
            ),
        )
        try:
            return json.loads(response.text)
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Workflow selection: happens BEFORE the graph is invoked (see the
    # architecture diagram in the project brief: entrypoint -> workflow
    # selection -> StateGraph). Kept here rather than in agent_llm.py so
    # ALL Gemini API calls stay inside the technique boundary, per
    # section 11 ("Gemini-specific API code belongs inside the
    # technique/LLM boundary").
    # ------------------------------------------------------------------
    async def select_workflow(self, user_request: str) -> str:
        prompt = (
            "Classify this EgyptAir customer service request into exactly "
            "one workflow. Return ONLY JSON: "
            '{"workflow": "flight_investigation"|"compensation"|"full_disruption"}\n\n'
            "flight_investigation: passenger just wants to know if a flight is "
            "disrupted/on time.\n"
            "compensation: passenger is asking about or requesting compensation "
            "for a disruption.\n"
            "full_disruption: an agent/ops user wants the complete disruption "
            "handling process (status + booking + policy + report) without a "
            "compensation payout.\n\n"
            f"Request: {user_request}"
        )
        result = await self._json_call(prompt)
        workflow = result.get("workflow")
        if workflow not in ("flight_investigation", "compensation", "full_disruption"):
            return "flight_investigation"  # safest default: read-only, no side effects
        return workflow

    # ------------------------------------------------------------------
    # Task decomposition: extract flight_number / booking_id / workflow
    # hint from a free-text user request. Used by the `decompose` node to
    # fill in state fields the caller didn't already supply.
    # ------------------------------------------------------------------
    async def decompose(self, user_request: str) -> dict[str, Any]:
        prompt = (
            "You are extracting structured fields from an EgyptAir customer "
            "service request. Return ONLY JSON with this exact shape:\n"
            '{"flight_number": string|null, "booking_id": integer|null, '
            '"intent_summary": string}\n\n'
            f"Request: {user_request}"
        )
        result = await self._json_call(prompt)
        return {
            "flight_number": result.get("flight_number"),
            "booking_id": result.get("booking_id"),
            "intent_summary": result.get("intent_summary", user_request),
        }

    # ------------------------------------------------------------------
    # Compensation reasoning: propose an amount/reason given real flight +
    # booking + retrieved policy context. Used by `compensation_reasoning`
    # node. This is a proposal only -- constrained_policy_check and, after
    # that, human_approval both gate it before anything is submitted.
    # ------------------------------------------------------------------
    async def compensation_reasoning(
        self,
        *,
        flight_status: dict[str, Any],
        booking_details: dict[str, Any],
        policy_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        policy_text = "\n".join(
            f"- ({p.get('metadata', {}).get('title', 'policy')}) {p.get('content', '')}"
            for p in policy_context
        )
        prompt = (
            "You are reasoning about EgyptAir passenger compensation. Base your "
            "decision ONLY on the flight status, booking, and policy excerpts "
            "below. Return ONLY JSON: "
            '{"eligible": boolean, "amount": number, "currency": string, '
            '"reason": string, "rationale": string}\n\n'
            f"Flight status: {json.dumps(flight_status)}\n"
            f"Booking: {json.dumps(booking_details)}\n"
            f"Policy excerpts:\n{policy_text}\n"
        )
        result = await self._json_call(
            prompt,
            system_instruction=(
                "Do not invent compensation amounts or rules that are not "
                "present in the provided policy excerpts."
            ),
        )
        result.setdefault("eligible", False)
        result.setdefault("amount", 0)
        result.setdefault("currency", "USD")
        result.setdefault("reason", "")
        result.setdefault("rationale", "")
        return result

    # ------------------------------------------------------------------
    # Constrained ReAct-style check: verify the proposed decision stays
    # within the retrieved policy bounds before it is ever shown to a
    # human for approval. Deliberately narrow/constrained (not a free
    # agent loop) -- it can only accept, cap, or reject.
    # ------------------------------------------------------------------
    async def constrained_policy_check(
        self,
        *,
        decision: dict[str, Any],
        policy_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        policy_text = "\n".join(p.get("content", "") for p in policy_context)
        prompt = (
            "You are a constrained policy checker. You may ONLY do one of: "
            "accept the amount as-is, cap it down to a policy-supported "
            "amount, or reject it. You may not increase the amount or invent "
            "a new reason. Return ONLY JSON: "
            '{"within_policy": boolean, "final_amount": number, '
            '"justification": string}\n\n'
            f"Proposed decision: {json.dumps(decision)}\n"
            f"Policy excerpts:\n{policy_text}\n"
        )
        result = await self._json_call(prompt)
        result.setdefault("within_policy", False)
        result.setdefault("final_amount", 0)
        result.setdefault("justification", "")
        return result
