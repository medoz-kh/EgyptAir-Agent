"""
routers.py -- deterministic transitions based on AgentState only.

Per project brief section 10: routers stay deterministic and focused on
workflow state. None of these call Gemini or any dependency -- they only
read `state`. If a routing decision ever needs reasoning, that reasoning
belongs in a node (writing a field to state) BEFORE the router reads it,
not inside the router itself.
"""

from __future__ import annotations

from state_graph.state import AgentState


def route_flight_status(state: AgentState) -> str:
    if state.get("error"):
        return "failure"
    return "evaluate_flight"


def route_after_evaluate_investigation(state: AgentState) -> str:
    """flight_investigation workflow: normal flights end early, disrupted
    flights get a report."""
    return "policy_retrieval" if state.get("is_disrupted") else "flight_normal"


def route_after_evaluate_disruption(state: AgentState) -> str:
    """full_disruption workflow: always proceeds to booking regardless of
    disruption status, since the caller already believes there's a
    disruption to process end-to-end."""
    return "get_booking"


def route_after_booking(state: AgentState) -> str:
    if state.get("error"):
        return "failure"
    return "policy_retrieval"


def route_compensation_decision(state: AgentState) -> str:
    if state.get("error"):
        return "failure"
    check = state.get("policy_check") or {}
    if not check.get("within_policy") or (check.get("final_amount") or 0) <= 0:
        return "complete"  # not eligible / no amount -- nothing to approve
    return "human_approval"


def route_human_decision(state: AgentState) -> str:
    if state.get("approval_status") == "approved":
        return "submit_compensation"
    return "compensation_rejected"


def route_after_submit(state: AgentState) -> str:
    if state.get("error"):
        return "failure"
    return "complete"
