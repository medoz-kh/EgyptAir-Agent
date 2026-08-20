"""
nodes.py -- one node = one workflow responsibility (project brief section 9).

Nodes never create their own MCP connection, Gemini client, or RAG
implementation. They only call `deps.*`. Each node is a small async
function `(state, deps) -> partial_state_update_dict`, built into a
LangGraph-compatible closure by `build_nodes(deps)` in workflows.py.

DISRUPTION THRESHOLD: a flight counts as disrupted if its status is
"Delayed" with delay_minutes >= 60, or "Cancelled". This number isn't
specified anywhere in the existing repo (no policy table lookup ties a
number to "disrupted" vs "normal") -- it's a reasonable default and is
called out here explicitly rather than buried, since it's the one place
this file invents a business rule instead of reading one.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from state_graph.dependencies import GraphDependencies
from state_graph.state import AgentState

DISRUPTION_DELAY_MINUTES = 60


def _trace(name: str) -> dict[str, Any]:
    return {"trace": [name]}


# ----------------------------------------------------------------------
# decompose
# ----------------------------------------------------------------------
async def decompose(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    """Fill flight_number/booking_id from the free-text request if the
    caller didn't already supply them. Uses the technique engine
    (reasoning), not a hand-rolled parser -- but never invents an
    orchestration decision; it only fills state fields."""
    if state.get("flight_number") and (
        state.get("workflow") == "flight_investigation" or state.get("booking_id")
    ):
        return _trace("decompose:skipped(already-specified)")

    try:
        extracted = await deps.technique.decompose(state["user_request"])
    except Exception as exc:  # technique engine failure shouldn't crash the graph
        return {"error": f"decompose failed: {exc}", **_trace("decompose:error")}

    update: dict[str, Any] = _trace("decompose")
    if not state.get("flight_number") and extracted.get("flight_number"):
        update["flight_number"] = extracted["flight_number"]
    if not state.get("booking_id") and extracted.get("booking_id"):
        update["booking_id"] = extracted["booking_id"]
    return update


# ----------------------------------------------------------------------
# get_flight_status
# ----------------------------------------------------------------------
async def get_flight_status(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    flight_number = state.get("flight_number")
    if not flight_number:
        return {
            "error": "No flight_number available to look up flight status.",
            **_trace("get_flight_status:error"),
        }

    result = await deps.call_tool("get_flight_status", {"flight_number": flight_number})

    if not result.get("found", False):
        return {
            "error": result.get("message", "Flight not found."),
            **_trace("get_flight_status:not_found"),
        }

    return {"flight_status": result, **_trace("get_flight_status")}


# ----------------------------------------------------------------------
# evaluate_flight
# ----------------------------------------------------------------------
async def evaluate_flight(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    status = state.get("flight_status") or {}
    flight_state = status.get("status")
    delay = status.get("delay_minutes") or 0

    is_disrupted = flight_state == "Cancelled" or (
        flight_state == "Delayed" and delay >= DISRUPTION_DELAY_MINUTES
    )
    return {"is_disrupted": is_disrupted, **_trace("evaluate_flight")}


# ----------------------------------------------------------------------
# get_booking
# ----------------------------------------------------------------------
async def get_booking(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    booking_id = state.get("booking_id")
    if not booking_id:
        return {
            "error": "No booking_id available to look up booking details.",
            **_trace("get_booking:error"),
        }

    result = await deps.call_tool("get_booking_details", {"booking_id": booking_id})

    if not result.get("found", False):
        return {
            "error": result.get("message", "Booking not found."),
            **_trace("get_booking:not_found"),
        }

    return {"booking_details": result, **_trace("get_booking")}


# ----------------------------------------------------------------------
# policy_retrieval
# ----------------------------------------------------------------------
async def policy_retrieval(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    """RAG is retrieval/grounding only -- it does not decide anything.
    Query is built from real state (flight status + booking), not just
    the raw user request, so retrieval is grounded in what actually
    happened rather than what the passenger said happened."""
    status = state.get("flight_status") or {}
    query_parts = [
        "EgyptAir compensation and disruption policy for",
        status.get("status", ""),
        f"delay of {status.get('delay_minutes', 0)} minutes" if status.get("delay_minutes") else "",
        state.get("user_request", ""),
    ]
    query = " ".join(p for p in query_parts if p).strip()

    try:
        hits = deps.rag_search(query, 3)
    except Exception as exc:
        return {"error": f"policy retrieval failed: {exc}", **_trace("policy_retrieval:error")}

    return {"policy_context": hits, **_trace("policy_retrieval")}


# ----------------------------------------------------------------------
# compensation_reasoning
# ----------------------------------------------------------------------
async def compensation_reasoning(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    try:
        decision = await deps.technique.compensation_reasoning(
            flight_status=state.get("flight_status") or {},
            booking_details=state.get("booking_details") or {},
            policy_context=state.get("policy_context") or [],
        )
    except Exception as exc:
        return {"error": f"compensation reasoning failed: {exc}", **_trace("compensation_reasoning:error")}

    return {"compensation_decision": decision, **_trace("compensation_reasoning")}


# ----------------------------------------------------------------------
# constrained_react (constrained policy-bounds check, not a free agent loop)
# ----------------------------------------------------------------------
async def constrained_react(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    decision = state.get("compensation_decision") or {}
    if not decision.get("eligible"):
        return {
            "policy_check": {"within_policy": False, "final_amount": 0, "justification": "Not eligible."},
            **_trace("constrained_react:not_eligible"),
        }

    try:
        check = await deps.technique.constrained_policy_check(
            decision=decision,
            policy_context=state.get("policy_context") or [],
        )
    except Exception as exc:
        return {"error": f"constrained policy check failed: {exc}", **_trace("constrained_react:error")}

    return {"policy_check": check, **_trace("constrained_react")}


# ----------------------------------------------------------------------
# human_approval -- the safety-critical gate. Uses LangGraph's interrupt()
# so the ENTIRE graph pauses and is checkpointed; nothing downstream runs
# until a human resumes the thread with an explicit decision.
# ----------------------------------------------------------------------
async def human_approval(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    decision = state.get("compensation_decision") or {}
    check = state.get("policy_check") or {}

    payload = interrupt(
        {
            "type": "compensation_approval_required",
            "booking_id": state.get("booking_id"),
            "proposed_amount": decision.get("amount"),
            "currency": decision.get("currency", "USD"),
            "reason": decision.get("reason"),
            "policy_capped_amount": check.get("final_amount"),
            "within_policy": check.get("within_policy"),
        }
    )

    # `payload` is whatever the caller passed to Command(resume=payload).
    decision_value = (payload or {}).get("decision") if isinstance(payload, dict) else None
    approved = decision_value == "approve"

    update: dict[str, Any] = {
        "approval_status": "approved" if approved else "rejected",
        "approval_notes": (payload or {}).get("notes", "") if isinstance(payload, dict) else "",
        **_trace("human_approval"),
    }
    if isinstance(payload, dict) and payload.get("employee_id"):
        update["employee_id"] = payload["employee_id"]
    if isinstance(payload, dict) and payload.get("manager_id"):
        update["manager_id"] = payload["manager_id"]
    return update


# ----------------------------------------------------------------------
# submit_compensation -- MUST only be reachable after human_approval sets
# approval_status == "approved" (enforced by routers.route_human_decision,
# not by this node -- this node has no way to run without that edge).
# Calls submit_compensation_request (creates the Pending record) then
# approve_compensation (the real MCP tool that finalizes it -- note this
# tool does its OWN ctx.elicit() confirmation on the MCP server side; the
# elicitation_callback that answers it is registered in agent/agent_llm.py).
# ----------------------------------------------------------------------
async def submit_compensation(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    check = state.get("policy_check") or {}
    decision = state.get("compensation_decision") or {}
    amount = check.get("final_amount") or decision.get("amount") or 0

    if not state.get("employee_id"):
        return {
            "error": "No employee_id available to submit compensation request.",
            **_trace("submit_compensation:error"),
        }

    submit_result = await deps.call_tool(
        "submit_compensation_request",
        {
            "args": {
                "employee_id": state["employee_id"],
                "booking_id": state["booking_id"],
                "requested_amount": amount,
                "reason": decision.get("reason", "Flight disruption compensation."),
            }
        },
    )

    if not submit_result.get("success"):
        return {
            "error": submit_result.get("message", "submit_compensation_request failed."),
            **_trace("submit_compensation:submit_failed"),
        }

    request_id = submit_result.get("request_id")
    update: dict[str, Any] = {
        "compensation_request_id": request_id,
        **_trace("submit_compensation:submitted"),
    }

    if state.get("manager_id"):
        approve_result = await deps.call_tool(
            "approve_compensation",
            {"args": {"employee_id": state["manager_id"], "request_id": request_id}},
        )
        update["compensation_result"] = approve_result
        if not approve_result.get("success"):
            update["error"] = approve_result.get("message", "approve_compensation failed.")
    else:
        update["compensation_result"] = {
            "success": True,
            "status": "Pending",
            "message": "Request submitted; awaiting manager approval via approve_compensation.",
        }

    return update


# ----------------------------------------------------------------------
# generate_report
# ----------------------------------------------------------------------
async def generate_report(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    try:
        report = await deps.call_tool("generate_disruption_report", {})
    except Exception as exc:
        return {"error": f"report generation failed: {exc}", **_trace("generate_report:error")}

    return {"disruption_report": report, **_trace("generate_report")}


# ----------------------------------------------------------------------
# terminal nodes
# ----------------------------------------------------------------------
async def flight_normal(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    return {
        "final_message": f"Flight {state.get('flight_number')} is operating normally.",
        **_trace("flight_normal"),
    }


async def failure(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    return {
        "final_message": f"Request could not be completed: {state.get('error')}",
        **_trace("failure"),
    }


async def compensation_rejected(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    return {
        "final_message": "Compensation request was not approved. No submission was made.",
        **_trace("compensation_rejected"),
    }


async def complete(state: AgentState, deps: GraphDependencies) -> dict[str, Any]:
    if state.get("final_message"):
        return _trace("complete")

    parts = []
    if state.get("compensation_result"):
        parts.append(f"Compensation: {state['compensation_result']}")
    if state.get("disruption_report"):
        parts.append(f"Report: {state['disruption_report']}")
    return {
        "final_message": " | ".join(parts) or "Workflow complete.",
        **_trace("complete"),
    }
