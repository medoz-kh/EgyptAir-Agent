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

from static_decomposition import build_static_disruption_plan


FLIGHT_NUMBER = "MS701"
BOOKING_ID = 1


async def main() -> None:
    plan = build_static_disruption_plan(
        f"Handle a flight disruption for flight {FLIGHT_NUMBER} "
        f"and affected booking {BOOKING_ID}."
    )

    print("\n" + "=" * 60)
    print("EGYPTAIR REAL MCP DAG TEST")
    print("=" * 60)

    print(f"\nGoal:\n{plan.goal}")
    print(f"\nExecution batches: {plan.execution_batches()}")

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
            available_tools = {
                tool.name for tool in tools_response.tools
            }

            print("\nAvailable MCP tools:")
            for tool_name in sorted(available_tools):
                print(f"  - {tool_name}")

            outputs: dict[str, str] = {}

            # ---------------------------------------------------------
            # BATCH 1
            # t1: Get flight status
            # ---------------------------------------------------------
            print("\n" + "-" * 60)
            print("BATCH 1")
            print("-" * 60)

            print(f"\n▶ t1: get_flight_status({FLIGHT_NUMBER})")

            if "get_flight_status" not in available_tools:
                raise RuntimeError(
                    "MCP tool 'get_flight_status' was not found."
                )

            result = await session.call_tool(
                name="get_flight_status",
                arguments={
                    "flight_number": FLIGHT_NUMBER,
                },
            )

            t1_output = extract_text(result)
            outputs["t1"] = t1_output

            print("\nResult:")
            print(t1_output)

            # ---------------------------------------------------------
            # BATCH 2
            # t2 + t3 can execute independently
            # ---------------------------------------------------------
            print("\n" + "-" * 60)
            print("BATCH 2 — PARALLEL")
            print("-" * 60)

            async def execute_t2() -> tuple[str, str]:
                print("\n▶ t2: get_booking_details")

                if "get_booking_details" not in available_tools:
                    raise RuntimeError(
                        "MCP tool 'get_booking_details' was not found."
                    )

                result = await session.call_tool(
                    name="get_booking_details",
                    arguments={
                        "booking_id": BOOKING_ID,
                    },
                )

                return "t2", extract_text(result)

            async def execute_t3() -> tuple[str, str]:
                print("\n▶ t3: read sql://policies")

                result = await session.read_resource(
                    "sql://policies"
                )

                return "t3", extract_resource_text(result)

            t2_result, t3_result = await asyncio.gather(
                execute_t2(),
                execute_t3(),
            )

            outputs[t2_result[0]] = t2_result[1]
            outputs[t3_result[0]] = t3_result[1]

            print("\nResult t2:")
            print(outputs["t2"])

            print("\nResult t3:")
            print(outputs["t3"])

            # ---------------------------------------------------------
            # BATCH 3
            # t4: Analyze real results
            # ---------------------------------------------------------
            print("\n" + "-" * 60)
            print("BATCH 3")
            print("-" * 60)

            print("\n▶ t4: Analyze disruption")

            t4_output = build_resolution_analysis(
                flight_output=outputs["t1"],
                booking_output=outputs["t2"],
                policy_output=outputs["t3"],
            )

            outputs["t4"] = t4_output

            print("\nResult:")
            print(t4_output)

            # ---------------------------------------------------------
            # BATCH 4
            # t5: Final synthesis
            # ---------------------------------------------------------
            print("\n" + "-" * 60)
            print("BATCH 4")
            print("-" * 60)

            print("\n▶ t5: Final resolution")

            t5_output = build_final_output(
                goal=plan.goal,
                flight_output=outputs["t1"],
                booking_output=outputs["t2"],
                policy_output=outputs["t3"],
                analysis_output=outputs["t4"],
            )

            outputs["t5"] = t5_output

            print("\n" + "=" * 60)
            print("FINAL RESULT")
            print("=" * 60)
            print(t5_output)

            print("\n" + "=" * 60)
            print("REAL DAG TEST: PASSED")
            print("=" * 60)


def extract_text(result) -> str:
    texts = []

    for content in result.content:
        if getattr(content, "type", None) == "text":
            texts.append(content.text)

    if not texts:
        return str(result)

    return "\n".join(texts)


def extract_resource_text(result) -> str:
    texts = []

    for content in result.contents:
        if hasattr(content, "text"):
            texts.append(content.text)

    if not texts:
        return str(result)

    return "\n".join(texts)


def build_resolution_analysis(
    flight_output: str,
    booking_output: str,
    policy_output: str,
) -> str:
    return (
        "DISRUPTION ANALYSIS\n\n"
        f"Flight information:\n{flight_output}\n\n"
        f"Booking information:\n{booking_output}\n\n"
        f"Policy information:\n{policy_output}\n\n"
        "The three required information branches have been successfully "
        "collected. The final resolution must be based only on these "
        "real MCP outputs and the supplied EgyptAir policy."
    )


def build_final_output(
    goal: str,
    flight_output: str,
    booking_output: str,
    policy_output: str,
    analysis_output: str,
) -> str:
    return (
        f"Goal:\n{goal}\n\n"
        "FINAL EGYPTAIR DISRUPTION RESULT\n\n"
        f"Flight:\n{flight_output}\n\n"
        f"Booking:\n{booking_output}\n\n"
        f"Policy:\n{policy_output}\n\n"
        f"Analysis:\n{analysis_output}\n"
    )


if __name__ == "__main__":
    asyncio.run(main())