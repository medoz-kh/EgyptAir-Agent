"""
state.py -- AgentState: the single piece of data that flows through every
StateGraph node. This is intentionally a flat TypedDict (LangGraph's native
shape) rather than a class hierarchy, so nodes can update it with plain
dict merges.

Field groups:
    - request metadata      : request_id, user_request, workflow
    - actor identity        : employee_id, manager_id (needed for MCP auth)
    - extracted targets     : flight_number, booking_id
    - tool results          : flight_status, booking_details
    - retrieval             : policy_context
    - reasoning             : compensation_decision, policy_check
    - HITL                  : approval_status, approval_notes
    - submission             : compensation_request_id, compensation_result
    - reporting              : disruption_report
    - terminal               : final_message, error
    - observability           : trace (append-only log of node names)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # request metadata
    request_id: str
    user_request: str
    workflow: str  # "flight_investigation" | "compensation" | "full_disruption"

    # actor identity (who is performing the action, for MCP tool authorization)
    employee_id: Optional[int]
    manager_id: Optional[int]

    # extracted targets (filled by the decompose node, or pre-set by the caller)
    flight_number: Optional[str]
    booking_id: Optional[int]

    # tool results
    flight_status: Optional[dict[str, Any]]
    is_disrupted: Optional[bool]
    booking_details: Optional[dict[str, Any]]

    # retrieval
    policy_context: Optional[list[dict[str, Any]]]

    # reasoning
    compensation_decision: Optional[dict[str, Any]]
    policy_check: Optional[dict[str, Any]]

    # HITL
    approval_status: Optional[str]  # "pending" | "approved" | "rejected"
    approval_notes: Optional[str]

    # submission
    compensation_request_id: Optional[int]
    compensation_result: Optional[dict[str, Any]]

    # reporting
    disruption_report: Optional[dict[str, Any]]

    # terminal
    final_message: Optional[str]
    error: Optional[str]

    # observability -- Annotated with operator.add so LangGraph appends
    # rather than overwrites across node updates.
    trace: Annotated[list[str], operator.add]


def new_state(
    *,
    request_id: str,
    user_request: str,
    workflow: str,
    employee_id: Optional[int] = None,
    manager_id: Optional[int] = None,
    flight_number: Optional[str] = None,
    booking_id: Optional[int] = None,
) -> AgentState:
    """Construct a fresh AgentState for a new workflow invocation."""
    return AgentState(
        request_id=request_id,
        user_request=user_request,
        workflow=workflow,
        employee_id=employee_id,
        manager_id=manager_id,
        flight_number=flight_number,
        booking_id=booking_id,
        flight_status=None,
        is_disrupted=None,
        booking_details=None,
        policy_context=None,
        compensation_decision=None,
        policy_check=None,
        approval_status=None,
        approval_notes=None,
        compensation_request_id=None,
        compensation_result=None,
        disruption_report=None,
        final_message=None,
        error=None,
        trace=[],
    )
