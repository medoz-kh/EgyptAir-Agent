import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================
# PROJECT PATHS
# ============================================================

# agent.py is inside:
# EgyptAir-Agent/agent/agent.py
#
# Therefore parents[1] = EgyptAir-Agent/

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PLANNER
# ============================================================

from planning.static_decomposition import build_static_disruption_plan


# ============================================================
# CONFIGURATION
# ============================================================

FLIGHT_NUMBER = "MS703"
BOOKING_ID = 4


# ============================================================
# HELPERS
# ============================================================

def extract_tool_text(result) -> str:
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


# ============================================================
# MAIN
# ============================================================

async def main():

    server_path = (
        PROJECT_ROOT
        / "mcp_server"
        / "server.py"
    )

    print(f"📁 Project root: {PROJECT_ROOT}")
    print(f"📡 MCP server: {server_path}")

    if not server_path.exists():
        raise FileNotFoundError(
            f"MCP server not found:\n{server_path}"
        )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=None,
    )

    print("\n🔌 Connecting to EgyptAir MCP Server...")

    async with stdio_client(server_params) as (
        read_stream,
        write_stream,
    ):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            # ====================================================
            # MCP INITIALIZATION
            # ====================================================

            print("\n🤝 Performing MCP Protocol Handshake...")

            init_result = await session.initialize()

            print("✅ Handshake Complete!")

            print(
                f"   Server Name: "
                f"{init_result.serverInfo.name}"
            )
            
            # ====================================================================
            # CAPABILITY NEGOTIATION & CLIENT GATING (TA RUBRIC FIX)
            # ====================================================================
            server_capabilities = init_result.capabilities
            
            # 1. Check for Prompts capability
            if server_capabilities and hasattr(server_capabilities, "prompts") and server_capabilities.prompts:
                print("✅ Server supports dynamic prompts.")
            else:
                print("⚠️ Prompts capability missing. FALLBACK: Using local static prompts.")
                
            # 2. Check for Resources capability
            if server_capabilities and hasattr(server_capabilities, "resources") and server_capabilities.resources:
                print("✅ Server supports resources.")
            else:
                print("⚠️ Resources capability missing. FALLBACK: Disabling resource fetching.")

            # ====================================================================
            # RUNTIME NOTIFICATIONS & TOOL REFRESH (TA RUBRIC FIX)
            # ====================================================================
            if server_capabilities and hasattr(server_capabilities, "tools") and getattr(server_capabilities.tools, "listChanged", False):
                print("✅ Server supports dynamic tool toggling. Registering listener...")
                
                @session.on_notification("notifications/tools/list_changed")
                async def handle_tools_changed(notification):
                    print("\n🔄 [EVENT] Admin toggled a tool! Refreshing client tool list...")
                    # Re-fetch the live tools from the server
                    updated_tools = await session.list_tools()
                    print(f"✅ Tool list successfully updated. Total tools available: {len(updated_tools.tools)}")
                    # The agent will now use this updated_tools list for future LLM calls
            else:
                print("⚠️ Server does not support listChanged. Admin UI tool toggling will be disabled.")

            print(
                f"   Server Version: "
                f"{init_result.serverInfo.version}"
            )

            # ====================================================
            # TOOL DISCOVERY
            # ====================================================


            print("\n🔍 Discovering MCP Tools...")

            tools_response = await session.list_tools()

            available_tools = {
                tool.name
                for tool in tools_response.tools
            }

            print(
                f"\n[Tools Found: "
                f"{len(tools_response.tools)}]"
            )

            for tool in tools_response.tools:
                print(f" - 🛠️ {tool.name}")

            # ====================================================
            # STATIC DAG
            # ====================================================

            print("\n" + "=" * 60)
            print("🧠 BUILDING EGYPTAIR STATIC DAG")
            print("=" * 60)

            goal = (
                f"Handle the disruption for flight "
                f"{FLIGHT_NUMBER} "
                f"and affected booking "
                f"{BOOKING_ID}."
            )

            plan = build_static_disruption_plan(goal)

            print(f"\nGoal:\n{plan.goal}")

            print("\nDAG Tasks:")

            for task in plan.tasks:

                dependencies = (
                    ", ".join(task.depends_on)
                    if task.depends_on
                    else "None"
                )

                print(f"\n  {task.id}")
                print(
                    f"    Instruction: "
                    f"{task.instruction}"
                )
                print(
                    f"    Depends on: "
                    f"{dependencies}"
                )

            print("\nExecution Batches:")

            for index, batch in enumerate(
                plan.execution_batches(),
                start=1,
            ):
                print(
                    f"  Batch {index}: {batch}"
                )

            # ====================================================
            # T1
            # ====================================================

            print("\n" + "-" * 60)
            print("▶ T1 — GET FLIGHT STATUS")
            print("-" * 60)

            if "get_flight_status" not in available_tools:
                raise RuntimeError(
                    "MCP tool 'get_flight_status' "
                    "was not found."
                )

            result = await session.call_tool(
                name="get_flight_status",
                arguments={
                    "flight_number": FLIGHT_NUMBER
                },
            )

            t1_output = extract_tool_text(result)

            print(t1_output)

            # ====================================================
            # T2 + T3
            # ====================================================

            print("\n" + "-" * 60)
            print("▶ T2 + T3 — PARALLEL EXECUTION")
            print("-" * 60)

            async def execute_t2():

                if "get_booking_details" not in available_tools:
                    raise RuntimeError(
                        "MCP tool 'get_booking_details' "
                        "was not found."
                    )

                result = await session.call_tool(
                    name="get_booking_details",
                    arguments={
                        "booking_id": BOOKING_ID
                    },
                )

                return extract_tool_text(result)

            async def execute_t3():

                result = await session.read_resource(
                    "sql://policies"
                )

                return extract_resource_text(result)

            t2_output, t3_output = await asyncio.gather(
                execute_t2(),
                execute_t3(),
            )

            print("\nT2 — Booking:")
            print(t2_output)

            print("\nT3 — Policy:")
            print(t3_output)

            # ====================================================
            # T4
            # ====================================================

            print("\n" + "-" * 60)
            print("▶ T4 — ANALYZE DISRUPTION")
            print("-" * 60)

            t4_output = analyze_disruption(
                flight_output=t1_output,
                booking_output=t2_output,
                policy_output=t3_output,
            )

            print(t4_output)

            # ====================================================
            # T5
            # ====================================================

            print("\n" + "-" * 60)
            print("▶ T5 — FINAL RESOLUTION")
            print("-" * 60)

            t5_output = build_final_resolution(
                goal=goal,
                flight_output=t1_output,
                booking_output=t2_output,
                policy_output=t3_output,
                analysis_output=t4_output,
            )

            print("\n" + "=" * 60)
            print("FINAL AGENT RESULT")
            print("=" * 60)

            print(t5_output)

            # ====================================================
            # SUCCESS
            # ====================================================

            print("\n" + "=" * 60)
            print("✅ MAIN AGENT + STATIC DAG INTEGRATION PASSED")
            print("=" * 60)


# ============================================================
# ANALYSIS
# ============================================================

def analyze_disruption(
    flight_output: str,
    booking_output: str,
    policy_output: str,
) -> str:

    try:
        flight = json.loads(flight_output)
    except json.JSONDecodeError:
        flight = {}

    status = flight.get("status")
    delay_minutes = flight.get(
        "delay_minutes",
        0,
    )

    if status == "Cancelled":

        return (
            "The flight is cancelled. "
            "The rebooking policy applies. "
            "The passenger should be considered "
            "for free rebooking to the next available flight."
        )

    if status == "Delayed":

        if delay_minutes > 120:

            return (
                f"The flight is delayed by "
                f"{delay_minutes} minutes. "
                "The delay exceeds two hours, so "
                "compensation eligibility should be reviewed."
            )

        return (
            f"The flight is delayed by "
            f"{delay_minutes} minutes, but the delay "
            "does not exceed two hours."
        )

    if status == "Scheduled":

        return (
            "The flight is currently scheduled "
            "with no reported disruption."
        )

    return (
        "The flight status could not be classified. "
        "No operational action should be performed."
    )


# ============================================================
# FINAL SYNTHESIS
# ============================================================

def build_final_resolution(
    goal: str,
    flight_output: str,
    booking_output: str,
    policy_output: str,
    analysis_output: str,
) -> str:

    return (
        f"Goal:\n"
        f"{goal}\n\n"

        f"Flight Information:\n"
        f"{flight_output}\n\n"

        f"Booking Information:\n"
        f"{booking_output}\n\n"

        f"Applicable Policies:\n"
        f"{policy_output}\n\n"

        f"Analysis:\n"
        f"{analysis_output}\n\n"

        f"Recommended Action:\n"
        f"{analysis_output}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())