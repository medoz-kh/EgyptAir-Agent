"""
workflows.py -- builds the three workflows from the project brief (section 8)
by wiring nodes.py + routers.py together with langgraph.graph.StateGraph.

Each node function in nodes.py takes (state, deps); here we close over a
single GraphDependencies instance (built once by runtime.py for the life
of the process) so the graphs LangGraph compiles only ever see the
standard `(state) -> partial_state` node signature it expects.

MUST NOT submit compensation before human approval: this is enforced
structurally, not by a flag -- there is no edge in the compensation graph
that reaches `submit_compensation` except through `human_approval` ->
`route_human_decision` -> "submit_compensation" (which only fires when
approval_status == "approved"). There is no other path into that node.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from state_graph import nodes, routers
from state_graph.dependencies import GraphDependencies
from state_graph.state import AgentState


def _bind(node_fn, deps: GraphDependencies):
    async def _wrapped(state: AgentState):
        return await node_fn(state, deps)

    _wrapped.__name__ = node_fn.__name__
    return _wrapped


def build_flight_investigation_workflow(deps: GraphDependencies):
    g = StateGraph(AgentState)

    g.add_node("decompose", _bind(nodes.decompose, deps))
    g.add_node("get_flight_status", _bind(nodes.get_flight_status, deps))
    g.add_node("evaluate_flight", _bind(nodes.evaluate_flight, deps))
    g.add_node("policy_retrieval", _bind(nodes.policy_retrieval, deps))
    g.add_node("generate_report", _bind(nodes.generate_report, deps))
    g.add_node("flight_normal", _bind(nodes.flight_normal, deps))
    g.add_node("failure", _bind(nodes.failure, deps))
    g.add_node("complete", _bind(nodes.complete, deps))

    g.add_edge(START, "decompose")
    g.add_edge("decompose", "get_flight_status")
    g.add_conditional_edges(
        "get_flight_status", routers.route_flight_status,
        {"evaluate_flight": "evaluate_flight", "failure": "failure"},
    )
    g.add_conditional_edges(
        "evaluate_flight", routers.route_after_evaluate_investigation,
        {"policy_retrieval": "policy_retrieval", "flight_normal": "flight_normal"},
    )
    g.add_edge("policy_retrieval", "generate_report")
    g.add_edge("generate_report", "complete")
    g.add_edge("flight_normal", "complete")
    g.add_edge("failure", END)
    g.add_edge("complete", END)

    return g


def build_compensation_workflow(deps: GraphDependencies):
    g = StateGraph(AgentState)

    g.add_node("decompose", _bind(nodes.decompose, deps))
    g.add_node("get_flight_status", _bind(nodes.get_flight_status, deps))
    g.add_node("get_booking", _bind(nodes.get_booking, deps))
    g.add_node("policy_retrieval", _bind(nodes.policy_retrieval, deps))
    g.add_node("compensation_reasoning", _bind(nodes.compensation_reasoning, deps))
    g.add_node("constrained_react", _bind(nodes.constrained_react, deps))
    g.add_node("human_approval", _bind(nodes.human_approval, deps))
    g.add_node("submit_compensation", _bind(nodes.submit_compensation, deps))
    g.add_node("generate_report", _bind(nodes.generate_report, deps))
    g.add_node("compensation_rejected", _bind(nodes.compensation_rejected, deps))
    g.add_node("failure", _bind(nodes.failure, deps))
    g.add_node("complete", _bind(nodes.complete, deps))

    g.add_edge(START, "decompose")
    g.add_edge("decompose", "get_flight_status")
    g.add_conditional_edges(
        "get_flight_status", routers.route_flight_status,
        {"evaluate_flight": "get_booking", "failure": "failure"},  # skip evaluate; compensation flow proceeds regardless of severity classification
    )
    g.add_conditional_edges(
        "get_booking", routers.route_after_booking,
        {"policy_retrieval": "policy_retrieval", "failure": "failure"},
    )
    g.add_edge("policy_retrieval", "compensation_reasoning")
    g.add_edge("compensation_reasoning", "constrained_react")
    g.add_conditional_edges(
        "constrained_react", routers.route_compensation_decision,
        {"human_approval": "human_approval", "complete": "complete", "failure": "failure"},
    )
    g.add_conditional_edges(
        "human_approval", routers.route_human_decision,
        {"submit_compensation": "submit_compensation", "compensation_rejected": "compensation_rejected"},
    )
    g.add_conditional_edges(
        "submit_compensation", routers.route_after_submit,
        {"complete": "generate_report", "failure": "failure"},
    )
    g.add_edge("generate_report", "complete")
    g.add_edge("compensation_rejected", "complete")
    g.add_edge("failure", END)
    g.add_edge("complete", END)

    return g


def build_full_disruption_workflow(deps: GraphDependencies):
    g = StateGraph(AgentState)

    g.add_node("decompose", _bind(nodes.decompose, deps))
    g.add_node("get_flight_status", _bind(nodes.get_flight_status, deps))
    g.add_node("evaluate_flight", _bind(nodes.evaluate_flight, deps))
    g.add_node("get_booking", _bind(nodes.get_booking, deps))
    g.add_node("policy_retrieval", _bind(nodes.policy_retrieval, deps))
    g.add_node("generate_report", _bind(nodes.generate_report, deps))
    g.add_node("failure", _bind(nodes.failure, deps))
    g.add_node("complete", _bind(nodes.complete, deps))

    g.add_edge(START, "decompose")
    g.add_edge("decompose", "get_flight_status")
    g.add_conditional_edges(
        "get_flight_status", routers.route_flight_status,
        {"evaluate_flight": "evaluate_flight", "failure": "failure"},
    )
    g.add_conditional_edges(
        "evaluate_flight", routers.route_after_evaluate_disruption,
        {"get_booking": "get_booking"},
    )
    g.add_conditional_edges(
        "get_booking", routers.route_after_booking,
        {"policy_retrieval": "policy_retrieval", "failure": "failure"},
    )
    g.add_edge("policy_retrieval", "generate_report")
    g.add_edge("generate_report", "complete")
    g.add_edge("failure", END)
    g.add_edge("complete", END)

    return g


WORKFLOW_BUILDERS = {
    "flight_investigation": build_flight_investigation_workflow,
    "compensation": build_compensation_workflow,
    "full_disruption": build_full_disruption_workflow,
}


def build_all_workflows(deps: GraphDependencies, checkpointer):
    """Compile all three workflows against a shared checkpointer.
    Returns {workflow_name: compiled_graph}."""
    return {
        name: builder(deps).compile(checkpointer=checkpointer)
        for name, builder in WORKFLOW_BUILDERS.items()
    }
