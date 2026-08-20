"""
runtime.py -- the adapter between external systems and StateGraph
(project brief section 12). Its ONLY job is to construct GraphDependencies
from real runtime resources that are created and owned by agent/agent_llm.py
(the MCP ClientSession, the RAG components, the Gemini client, the
MemoryManager). It must not create duplicate MCP/RAG systems -- it wraps
what it's given.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from mcp import ClientSession

from state_graph.dependencies import GraphDependencies
from state_graph.technique_engine import DEFAULT_MODEL_ID, GeminiTechniqueEngine


def _parse_tool_result(result) -> dict[str, Any]:
    """MCP tool results arrive as content blocks (usually a single text
    block containing JSON, since the fastmcp tools here return plain
    dicts that fastmcp serializes). Fall back to a raw-text wrapper if it
    isn't JSON so a node never crashes on an unexpected shape."""
    texts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
    joined = "\n".join(texts)
    if not joined:
        return {}
    try:
        return json.loads(joined)
    except (json.JSONDecodeError, TypeError):
        return {"raw_text": joined}


def _parse_resource_result(result) -> str:
    texts = [c.text for c in result.contents if hasattr(c, "text")]
    return "\n".join(texts)


def build_graph_dependencies(
    *,
    session: ClientSession,
    genai_client,
    hybrid_rag,
    guardrail=None,
    memory,
    model_id: str = DEFAULT_MODEL_ID,
) -> GraphDependencies:
    """
    session       : an already-initialized mcp.ClientSession (real MCP boundary)
    genai_client  : an already-constructed google.genai.Client
    hybrid_rag    : an already-constructed rag.hybrid_rag.HybridRAGSearch
                    (built on top of an already-seeded VectorStoreManager)
    guardrail      : optional rag.self_rag.GroundingGuardrail, for
                       answer_with_grounding (not required by the 3
                       structured workflows, but wired through for a
                       future free-text policy Q&A node)
    memory          : an already-constructed mcp_server.memory.manger.MemoryManager
    """

    async def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await session.call_tool(name=name, arguments=args)
        return _parse_tool_result(result)

    async def read_resource(uri: str) -> str:
        result = await session.read_resource(uri)
        return _parse_resource_result(result)

    def rag_search(query: str, n_results: int = 3) -> list[dict[str, Any]]:
        return hybrid_rag.search(query, n_results=n_results)

    answer_with_grounding = (
        guardrail.answer_with_grounding_check if guardrail is not None else None
    )

    technique = GeminiTechniqueEngine(genai_client, model_id=model_id)

    return GraphDependencies(
        call_tool=call_tool,
        read_resource=read_resource,
        rag_search=rag_search,
        answer_with_grounding=answer_with_grounding,
        technique=technique,
        memory=memory,
    )
