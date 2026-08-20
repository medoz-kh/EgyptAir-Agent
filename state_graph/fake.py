"""
fake.py -- FakeMCP / FakeTechniqueEngine, for tests ONLY (project brief
section 4/11: "FakeMCP is acceptable only inside tests" / "FakeTechniques
may exist in tests for isolated testing. They must not replace the real
Gemini technique engine in production."). Nothing in agent/agent_llm.py
imports this module.
"""

from __future__ import annotations

from typing import Any


class FakeMCP:
    """Canned MCP tool responses keyed by tool name, for graph-shape tests
    that don't need a real MCP server subprocess."""

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, args))
        return self.responses.get(name, {"found": False, "success": False, "message": "no fake response configured"})

    async def read_resource(self, uri: str) -> str:
        return "[]"


class FakeTechniqueEngine:
    """Deterministic stand-in for GeminiTechniqueEngine."""

    def __init__(
        self,
        *,
        decompose_result: dict[str, Any] | None = None,
        compensation_result: dict[str, Any] | None = None,
        policy_check_result: dict[str, Any] | None = None,
    ):
        self._decompose_result = decompose_result or {}
        self._compensation_result = compensation_result or {
            "eligible": True, "amount": 150, "currency": "USD",
            "reason": "Flight cancelled.", "rationale": "Cancellation policy applies.",
        }
        self._policy_check_result = policy_check_result or {
            "within_policy": True, "final_amount": 150, "justification": "Within cap.",
        }

    async def select_workflow(self, user_request: str) -> str:
        return "compensation"

    async def decompose(self, user_request: str) -> dict[str, Any]:
        return self._decompose_result

    async def compensation_reasoning(self, **kwargs) -> dict[str, Any]:
        return self._compensation_result

    async def constrained_policy_check(self, **kwargs) -> dict[str, Any]:
        return self._policy_check_result


class FakeMemory:
    def add_turn(self, role: str, content: str):
        pass

    def update_goal(self, goal: str):
        pass

    def consolidate(self):
        pass
