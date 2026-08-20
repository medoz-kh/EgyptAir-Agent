"""
persistence.py -- workflow execution/checkpoint state, per project brief
section 13. This is deliberately separate from mcp_server/memory
(MemoryManager), which stores agent experience/context, not workflow
execution state. Do not merge the two.

The compensation workflow contains a human_approval node that calls
LangGraph's `interrupt()`. That requires a checkpointer so the graph can
be paused, persisted, and resumed on the same thread_id after a human
supplies a decision. flight_investigation and full_disruption don't
strictly need one (no interrupt), but we checkpoint them too for
consistency and so a crashed run could in principle be inspected/resumed.

Two backends:
    - MemorySaver   : in-process, non-durable. Fine for a single
                       long-running process (e.g. the REPL in agent_llm.py).
    - SqliteSaver    : durable across process restarts. Used when
                        `langgraph-checkpoint-sqlite` is installed and a
                        db path is provided. Falls back to MemorySaver with
                        a printed warning if the optional dependency isn't
                        available, rather than hard-failing.
"""

from __future__ import annotations

import uuid
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver


def new_thread_id(prefix: str = "req") -> str:
    """A fresh thread id for one workflow invocation (one HITL cycle)."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def get_checkpointer(kind: str = "memory", db_path: Optional[str] = None):
    """
    Build a LangGraph checkpointer.

    kind="memory" (default) -> MemorySaver, always available.
    kind="sqlite"            -> durable SqliteSaver if the optional
                                 langgraph-checkpoint-sqlite package is
                                 installed; otherwise falls back to
                                 MemorySaver and prints a warning instead
                                 of crashing the agent.
    """
    if kind == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            path = db_path or "./state_graph_checkpoints.sqlite"
            # SqliteSaver.from_conn_string returns a context manager in some
            # langgraph versions; callers that need the durable path should
            # use that form directly. For the simple case we open a plain
            # connection.
            import sqlite3

            conn = sqlite3.connect(path, check_same_thread=False)
            return SqliteSaver(conn)
        except ImportError:
            print(
                "⚠️  langgraph-checkpoint-sqlite not installed -- "
                "falling back to in-memory checkpointing. HITL state will "
                "NOT survive a process restart. Install "
                "`langgraph-checkpoint-sqlite` for durable checkpoints."
            )
            return MemorySaver()

    return MemorySaver()
