"""
state_graph
===========

Workflow / orchestration layer for the EgyptAir Autonomous Agent.

This package owns ONLY orchestration. It does not implement Gemini calls,
MCP transport, RAG retrieval, or memory storage itself -- it depends on
those through `GraphDependencies` (see dependencies.py), which is built
by `runtime.py` from the *real* systems that already exist elsewhere in
this repo (mcp_server/, rag/, mcp_server/memory/).

Layering:
    state.py         -> AgentState (the data that flows through the graph)
    dependencies.py  -> GraphDependencies (capability boundary; nodes only see this)
    technique_engine.py -> GeminiTechniqueEngine (reasoning/planning, NOT orchestration)
    nodes.py          -> one node = one workflow responsibility
    routers.py        -> deterministic edge selection based on AgentState
    persistence.py     -> checkpointer for HITL interrupt/resume
    workflows.py       -> wires nodes+routers into the 3 compiled StateGraphs
    runtime.py          -> adapter: real MCP/RAG/Gemini/Memory -> GraphDependencies
    fake.py              -> FakeMCP / FakeTechniqueEngine for tests ONLY
"""
