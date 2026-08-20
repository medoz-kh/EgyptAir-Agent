"""
dependencies.py -- GraphDependencies is the ONLY way nodes reach the outside
world. Nodes must never import mcp/google.genai/chromadb/MemoryManager
directly -- they call `deps.call_tool(...)`, `deps.rag_search(...)`,
`deps.technique.decompose(...)`, `deps.memory.add_turn(...)`, etc.

This keeps the boundary from section 9/12 of the project brief real:
"They receive capabilities through GraphDependencies" and "The graph
should not know the implementation details of Gemini / MCP / RAG."

Concrete instances are built in runtime.py (real) or fake.py (tests only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Protocol


class TechniqueEngine(Protocol):
    """Structural type for GeminiTechniqueEngine / FakeTechniqueEngine."""

    async def select_workflow(self, user_request: str) -> str: ...

    async def decompose(self, user_request: str) -> dict[str, Any]: ...

    async def compensation_reasoning(
        self,
        *,
        flight_status: dict[str, Any],
        booking_details: dict[str, Any],
        policy_context: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    async def constrained_policy_check(
        self,
        *,
        decision: dict[str, Any],
        policy_context: list[dict[str, Any]],
    ) -> dict[str, Any]: ...


@dataclass
class GraphDependencies:
    """Capability boundary passed to every node via graph config."""

    # MCP tool boundary -- wraps ClientSession.call_tool and returns a plain
    # dict (already parsed from MCP content blocks). Never call MCP directly
    # from a node.
    call_tool: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]

    # MCP resource boundary
    read_resource: Callable[[str], Awaitable[str]]

    # RAG boundary -- synchronous hybrid (dense+BM25) search over policies
    rag_search: Callable[[str, int], list[dict[str, Any]]]

    # RAG boundary -- grounded answer with draft/critique/retry, for
    # free-text policy questions (not used by the structured workflows,
    # available for a future "policy_question" node / direct Q&A path)
    answer_with_grounding: Optional[Callable[[str, int], Awaitable[str]]]

    # Gemini reasoning/planning boundary
    technique: TechniqueEngine

    # Memory boundary (mcp_server.memory.manger.MemoryManager instance)
    memory: Any
