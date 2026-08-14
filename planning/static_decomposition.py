from __future__ import annotations

import sys
from pathlib import Path

# Make the reference toolkit available when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_TOOLKIT = PROJECT_ROOT / "external" / "task_decomposition_and_planning"

if str(REFERENCE_TOOLKIT) not in sys.path:
    sys.path.insert(0, str(REFERENCE_TOOLKIT))

from planning_lab.models import Plan, Task


def build_static_disruption_plan(
    goal: str,
) -> Plan:
    """
    Build the fixed EgyptAir flight-disruption DAG.

    This is intentionally STATIC:
    the structure of the DAG is predefined and does not
    ask an LLM to invent the task dependencies.
    """

    tasks = [
        Task(
            id="t1",
            instruction=(
                "Retrieve the current flight status and schedule "
                "for the affected EgyptAir flight."
            ),
            depends_on=[],
        ),
        Task(
            id="t2",
            instruction=(
                "Retrieve the booking and passenger information "
                "affected by the disrupted flight."
            ),
            depends_on=["t1"],
        ),
        Task(
            id="t3",
            instruction=(
                "Retrieve the applicable EgyptAir compensation "
                "and disruption policy."
            ),
            depends_on=["t1"],
        ),
        Task(
            id="t4",
            instruction=(
                "Analyze the flight status, affected booking information, "
                "and applicable policy to determine the appropriate resolution."
            ),
            depends_on=["t2", "t3"],
        ),
        Task(
            id="t5",
            instruction=(
                "Produce the final recommended resolution for the "
                "flight disruption based on all previous results."
            ),
            depends_on=["t4"],
        ),
    ]

    return Plan(
        goal=goal,
        tasks=tasks,
    )


def print_plan(plan: Plan) -> None:
    """Print the DAG in a human-readable form."""

    print("\n" + "=" * 60)
    print("EGYPTAIR STATIC DAG")
    print("=" * 60)

    print(f"\nGoal:\n{plan.goal}")

    print("\nTasks:")
    for task in plan.tasks:
        dependencies = task.depends_on or ["None"]

        print(f"\n  {task.id}")
        print(f"    Instruction: {task.instruction}")
        print(f"    Depends on: {', '.join(dependencies)}")

    print("\nExecution batches:")
    for index, batch in enumerate(plan.execution_batches(), start=1):
        print(f"  Batch {index}: {batch}")

    print("\nTopological order:")
    print(f"  {plan.topological_order()}")

    print("\nTerminal task:")
    print(f"  {plan.terminal_tasks()}")

    print("\n" + "=" * 60)
    print("STATIC DAG VALIDATION: PASSED")
    print("=" * 60)


if __name__ == "__main__":
    goal = "Handle a flight disruption for an affected EgyptAir passenger."

    plan = build_static_disruption_plan(goal)

    print_plan(plan)