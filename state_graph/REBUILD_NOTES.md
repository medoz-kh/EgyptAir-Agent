# state_graph/ rebuild notes

## What was actually in the repo vs. what the project brief assumed

The brief describes `state_graph/` as an existing subsystem with
`state.py`, `nodes.py`, `routers.py`, `workflows.py`, `runtime.py`,
`persistence.py`, and `tests/`. **None of that existed.** There was no
`langgraph` dependency in `requirements.txt`, no `GraphDependencies`, no
`GeminiTechniqueEngine` class. What was real and unchanged:

- `mcp_server/` — 5 real tools: `get_flight_status`, `get_booking_details`,
  `submit_compensation_request`, `approve_compensation`,
  `generate_disruption_report`, plus the `sql://policies` resource.
  (No `get_compensation_policy` or `draft_passenger_email` tools exist —
  the brief lists them but they're not implemented anywhere.)
- `rag/` — `VectorStoreManager`, `HybridRAGSearch`, `SelfRAGVerifier`,
  `GroundingGuardrail`.
- `mcp_server/memory/` — `MemoryManager` (`add_turn`, `update_goal`,
  `update_plan`, `update_tool`, `update_intermediate_state`, `consolidate`).
- `agent/agent_llm.py` — the old direct Gemini-function-call loop the
  brief explicitly says must not be the orchestrator. Preserved,
  unmodified, as `agent/agent_llm_legacy_direct_loop.py`.

This package (`state_graph/`) was built from scratch, wired to those real
modules, not invented in isolation.

## Design decisions worth knowing about (things the brief didn't resolve)

1. **Two separate HITL gates, not one.** `approve_compensation` does its
   own synchronous `ctx.elicit()` confirmation *inside the MCP tool* —
   that's a manager-facing gate baked into the tool itself. The
   `human_approval` graph node is a *different* gate: it decides whether
   the workflow proceeds to call `submit_compensation_request` at all,
   using LangGraph's `interrupt()`/checkpointer so the whole graph pauses
   (not just one tool call) and can be resumed on the same `thread_id`
   later, possibly from a different process. `submit_compensation` (the
   node) calls both tools in sequence, in that order.
2. **Disruption threshold.** No policy row ties a number to "disrupted."
   `nodes.DISRUPTION_DELAY_MINUTES = 60` (Cancelled always counts) is a
   default, isolated at the top of `nodes.py` so it's easy to find and
   change.
3. **Workflow selection lives in `GeminiTechniqueEngine.select_workflow`**,
   not in `agent_llm.py`, so every Gemini call stays inside the technique
   boundary per section 11 of the brief, even though the architecture
   diagram draws "workflow selection" before the StateGraph box.
4. **Demo actor identity.** `submit_compensation_request` /
   `approve_compensation` require `employee_id` / `manager_id` for MCP
   authorization. There's no auth layer in the repo, so `agent_llm.py`
   uses `DEMO_EMPLOYEE_ID` / `DEMO_MANAGER_ID` env vars (default 1/2) —
   flagged, not hidden. A real deployment sources these from an
   authenticated session.

## What I could not verify in this sandbox

- **No network access here** — I could not `pip install langgraph` or
  run the tests. The code follows the documented `interrupt()` /
  `Command(resume=...)` API, but run
  `pip install -r requirements.txt && pytest state_graph/tests/ -v`
  yourself before trusting it.
- **`ElicitResult(content={"value": bool})`** in `agent_llm.py`'s
  `elicitation_handler` — the exact content-key convention depends on
  your installed `mcp`/`fastmcp` SDK version's boolean elicitation
  schema, which isn't visible from source alone. Flagged in a comment at
  the call site; verify against your installed version.

## How to run

```bash
pip install -r requirements.txt
pytest state_graph/tests/ -v          # fake-backed, no real MCP/Gemini needed
python -m agent.agent_llm             # real run (needs GEMINI_API_KEY)
```

## What's still open (see "Definition of Done" in the original brief)

- End-to-end run against the real MCP server + real Gemini has not been
  executed (no network in this sandbox to install/run it).
- `flight_investigation` and `full_disruption` have no test coverage yet
  (only `compensation`, since that's the safety-critical one). Same
  `fake.py` pattern extends to them easily.
- Durable (sqlite) checkpointing is wired but untested — `agent_llm.py`
  currently uses `persistence.get_checkpointer("memory")`, non-durable
  across process restarts. Switch to `"sqlite"` once you've confirmed the
  optional dependency installs cleanly in your environment.
