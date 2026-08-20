"""
Smoke tests for state_graph using FakeMCP/FakeTechniqueEngine (test-only,
per project brief section 4/11). These do NOT start a real MCP server or
call the real Gemini API -- they test graph SHAPE and the safety property:

    submit_compensation_request must never be called before a human
    approves, and rejecting must never call it at all.

Run with: pytest state_graph/tests/test_workflows_fake.py -v
"""

import asyncio

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from state_graph.dependencies import GraphDependencies
from state_graph.fake import FakeMCP, FakeMemory, FakeTechniqueEngine
from state_graph.state import new_state
from state_graph.workflows import build_compensation_workflow


def _make_deps(fake_mcp: FakeMCP, technique: FakeTechniqueEngine) -> GraphDependencies:
    return GraphDependencies(
        call_tool=fake_mcp.call_tool,
        read_resource=fake_mcp.read_resource,
        rag_search=lambda q, n=3: [{"content": "Cancelled flights get $150.", "metadata": {"title": "Cancellation Policy"}}],
        answer_with_grounding=None,
        technique=technique,
        memory=FakeMemory(),
    )


def _base_mcp_responses():
    return {
        "get_flight_status": {
            "found": True, "flight_number": "MS703", "status": "Cancelled", "delay_minutes": 0,
        },
        "get_booking_details": {
            "found": True, "booking_id": 4, "passenger_name": "Test Passenger",
        },
        "submit_compensation_request": {
            "success": True, "request_id": 99, "status": "Pending",
        },
        "approve_compensation": {
            "success": True, "request_id": 99, "status": "Approved",
        },
    }


def test_reject_never_submits():
    fake_mcp = FakeMCP(_base_mcp_responses())
    deps = _make_deps(fake_mcp, FakeTechniqueEngine())
    graph = build_compensation_workflow(deps).compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "test-reject-1"}}
    initial = new_state(
        request_id="r1", user_request="My flight was cancelled",
        workflow="compensation", employee_id=1, manager_id=2,
        flight_number="MS703", booking_id=4,
    )

    result = asyncio.run(graph.ainvoke(initial, config=config))
    assert "__interrupt__" in result, "expected the graph to pause for human_approval"

    result = asyncio.run(graph.ainvoke(Command(resume={"decision": "reject"}), config=config))

    assert result["approval_status"] == "rejected"
    assert result["final_message"].startswith("Compensation request was not approved")
    tool_names_called = [name for name, _ in fake_mcp.calls]
    assert "submit_compensation_request" not in tool_names_called
    assert "approve_compensation" not in tool_names_called


def test_approve_submits_and_finalizes():
    fake_mcp = FakeMCP(_base_mcp_responses())
    deps = _make_deps(fake_mcp, FakeTechniqueEngine())
    graph = build_compensation_workflow(deps).compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "test-approve-1"}}
    initial = new_state(
        request_id="r2", user_request="My flight was cancelled",
        workflow="compensation", employee_id=1, manager_id=2,
        flight_number="MS703", booking_id=4,
    )

    result = asyncio.run(graph.ainvoke(initial, config=config))
    assert "__interrupt__" in result

    tool_names_called_before_resume = [name for name, _ in fake_mcp.calls]
    assert "submit_compensation_request" not in tool_names_called_before_resume

    result = asyncio.run(graph.ainvoke(Command(resume={"decision": "approve"}), config=config))

    assert result["approval_status"] == "approved"
    assert result["compensation_request_id"] == 99
    tool_names_called = [name for name, _ in fake_mcp.calls]
    assert "submit_compensation_request" in tool_names_called
    assert "approve_compensation" in tool_names_called
    # submit must come before approve, and both strictly after the interrupt/resume
    assert tool_names_called.index("submit_compensation_request") < tool_names_called.index("approve_compensation")


def test_not_eligible_skips_approval_entirely():
    fake_mcp = FakeMCP(_base_mcp_responses())
    technique = FakeTechniqueEngine(
        compensation_result={"eligible": False, "amount": 0, "currency": "USD", "reason": "", "rationale": ""},
    )
    deps = _make_deps(fake_mcp, technique)
    graph = build_compensation_workflow(deps).compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "test-ineligible-1"}}
    initial = new_state(
        request_id="r3", user_request="Minor delay question",
        workflow="compensation", employee_id=1, manager_id=2,
        flight_number="MS703", booking_id=4,
    )

    result = asyncio.run(graph.ainvoke(initial, config=config))
    assert "__interrupt__" not in result
    tool_names_called = [name for name, _ in fake_mcp.calls]
    assert "submit_compensation_request" not in tool_names_called
