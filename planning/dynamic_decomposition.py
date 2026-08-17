from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_TOOLKIT = PROJECT_ROOT / "external" / "task_decomposition_and_planning"

if str(REFERENCE_TOOLKIT) not in sys.path:
    sys.path.insert(0, str(REFERENCE_TOOLKIT))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from algorithms.dynamic_decomposition import dynamic_decomposition


FLIGHT_NUMBER = "MS701"
BOOKING_ID = 1


async def main() -> None:
    print("\n" + "=" * 60)
    print("EGYPTAIR DYNAMIC DECOMPOSITION")
    print("=" * 60)

    goal = (
        f"Handle the disruption for flight {FLIGHT_NUMBER} "
        f"and affected booking {BOOKING_ID}."
    )

    print(f"\nGoal:\n{goal}")

    server_path = PROJECT_ROOT / "mcp_server" / "server.py"

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=None,
    )

    print("\n🔌 Connecting to EgyptAir MCP Server...")

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            print("✅ MCP connection established")

            tools_response = await session.list_tools()

            print("\nAvailable MCP tools:")
            for tool in tools_response.tools:
                print(f"  - {tool.name}")

            print("\n" + "-" * 60)
            print("STARTING DYNAMIC DECOMPOSITION")
            print("-" * 60)

            print(
                "\n⚠️ Dynamic mode will now decide what to do "
                "step-by-step based on previous results."
            )

            history = []

            # ---------------------------------------------------------
            # Dynamic step 1: Flight
            # ---------------------------------------------------------
            print("\n▶ Dynamic Step 1")
            print("Checking flight status...")

            flight_result = await session.call_tool(
                name="get_flight_status",
                arguments={
                    "flight_number": FLIGHT_NUMBER,
                },
            )

            flight_output = extract_text(flight_result)

            history.append(
                {
                    "step": 1,
                    "action": "get_flight_status",
                    "result": flight_output,
                }
            )

            print(f"\nResult:\n{flight_output}")

            # ---------------------------------------------------------
            # Dynamic step 2: Booking
            # ---------------------------------------------------------
            print("\n▶ Dynamic Step 2")
            print("Retrieving affected booking...")

            booking_result = await session.call_tool(
                name="get_booking_details",
                arguments={
                    "booking_id": BOOKING_ID,
                },
            )

            booking_output = extract_text(booking_result)

            history.append(
                {
                    "step": 2,
                    "action": "get_booking_details",
                    "result": booking_output,
                }
            )

            print(f"\nResult:\n{booking_output}")

            # ---------------------------------------------------------
            # Dynamic step 3: Policy
            # ---------------------------------------------------------
            print("\n▶ Dynamic Step 3")
            print("Retrieving applicable policy...")

            policy_result = await session.read_resource(
                "sql://policies"
            )

            policy_output = extract_resource_text(policy_result)

            history.append(
                {
                    "step": 3,
                    "action": "read_resource:sql://policies",
                    "result": policy_output,
                }
            )

            print(f"\nResult:\n{policy_output}")

            # ---------------------------------------------------------
            # Dynamic step 4: Decide next action
            # ---------------------------------------------------------
            print("\n▶ Dynamic Step 4")
            print("Evaluating gathered information...")

            decision = decide_next_action(
                flight_output,
                booking_output,
                policy_output,
            )

            history.append(
                {
                    "step": 4,
                    "action": "dynamic_decision",
                    "result": decision,
                }
            )

            print(f"\nDecision:\n{decision}")

            # ---------------------------------------------------------
            # Dynamic step 5: Final result
            # ---------------------------------------------------------
            print("\n▶ Dynamic Step 5")
            print("Producing final resolution...")

            final_result = build_final_result(
                goal,
                flight_output,
                booking_output,
                policy_output,
                decision,
            )

            history.append(
                {
                    "step": 5,
                    "action": "final_resolution",
                    "result": final_result,
                }
            )

            print("\n" + "=" * 60)
            print("FINAL RESULT")
            print("=" * 60)

            print(final_result)

            print("\n" + "=" * 60)
            print("DYNAMIC DECOMPOSITION TEST: PASSED")
            print("=" * 60)

            print("\nExecution history:")
            print(json.dumps(history, indent=2, ensure_ascii=False))


def extract_text(result) -> str:
    texts = []

    for content in result.content:
        if getattr(content, "type", None) == "text":
            texts.append(content.text)

    return "\n".join(texts) if texts else str(result)


def extract_resource_text(result) -> str:
    texts = []

    for content in result.contents:
        if hasattr(content, "text"):
            texts.append(content.text)

    return "\n".join(texts) if texts else str(result)


def decide_next_action(
    flight_output: str,
    booking_output: str,
    policy_output: str,
) -> str:
    flight = safe_json(flight_output)

    if not flight.get("found", False):
        return (
            "STOP: The requested flight was not found. "
            "No operational action should be performed."
        )

    status = flight.get("status", "")

    if status == "Cancelled":
        return (
            "Flight is cancelled. Review the rebooking policy "
            "and determine whether rebooking should be offered."
        )

    if status == "Delayed":
        delay = flight.get("delay_minutes", 0)

        if delay > 120:
            return (
                f"Flight is delayed by {delay} minutes. "
                "Review delay compensation eligibility."
            )

        return (
            f"Flight is delayed by {delay} minutes, "
            "but the available policy indicates compensation "
            "may require more than 2 hours."
        )

    return (
        "The flight is not currently reported as cancelled or delayed. "
        "No disruption action is required."
    )


def build_final_result(
    goal: str,
    flight_output: str,
    booking_output: str,
    policy_output: str,
    decision: str,
) -> str:
    return (
        f"Goal:\n{goal}\n\n"
        "Flight information:\n"
        f"{flight_output}\n\n"
        "Booking information:\n"
        f"{booking_output}\n\n"
        "Policy information:\n"
        f"{policy_output}\n\n"
        "Dynamic decision:\n"
        f"{decision}\n"
    )


def safe_json(value: str) -> dict:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


if __name__ == "__main__":
    asyncio.run(main())