from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from external.task_decomposition_and_planning.planning_lab.models import Plan


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp_server" / "server.py"
ENV_PATH = ROOT / "mcp_server" / ".env"

MODEL_ID = "gemini-3.1-flash-lite"


PLANNER_PROMPT = """
You are the task decomposition planner for an EgyptAir customer-service agent.

Decompose the user's goal into a small executable DAG.

Rules:
- Create 3 to 6 tasks.
- Every task must contribute directly to the goal.
- Use dependencies when one task needs another task's result.
- Independent tasks should have no dependency on each other.
- The plan must contain exactly one final synthesis task.
- The final synthesis task must depend on every necessary branch.
- Task instructions must be concrete.
- Only request an EgyptAir MCP operation when the required arguments
  are explicitly available in the user's goal.
- Never invent flight numbers, booking IDs, employee IDs, amounts, or
  other values.
"""


SYNTHESIS_PROMPT = """
You are the final synthesis agent for an EgyptAir customer-service task.

Use ONLY:
1. The original goal.
2. The outputs produced by the executed plan.

Do not invent facts.

Give a concise final answer that directly addresses the original goal.
"""


def load_environment() -> str:
    load_dotenv(ENV_PATH)

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            f"GEMINI_API_KEY was not found in {ENV_PATH}"
        )

    return api_key


def create_gemini_client() -> genai.Client:
    api_key = load_environment()
    return genai.Client(api_key=api_key)


async def connect_mcp():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        env=dict(os.environ),
    )

    return stdio_client(server_params)


async def call_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:

    result = await session.call_tool(
        name=tool_name,
        arguments=arguments,
    )

    text_parts = []

    for content in result.content:
        if getattr(content, "type", None) == "text":
            text_parts.append(content.text)

    text = "\n".join(text_parts)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def extract_flight_number(instruction: str) -> str | None:
    match = re.search(
        r"\b[A-Za-z]{2}\d{3,4}\b",
        instruction,
    )

    if match:
        return match.group(0).upper()

    return None


def extract_booking_id(instruction: str) -> int | None:
    match = re.search(
        r"\bbooking(?:\s+id)?\s*[:#]?\s*(\d+)\b",
        instruction,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


def task_to_tool_call(
    instruction: str,
) -> tuple[str, dict[str, Any]] | None:

    text = instruction.lower()

    if "flight status" in text:
        flight_number = extract_flight_number(instruction)

        if flight_number is None:
            return None

        return (
            "get_flight_status",
            {
                "flight_number": flight_number,
            },
        )

    if "booking details" in text:
        booking_id = extract_booking_id(instruction)

        if booking_id is None:
            return None

        return (
            "get_booking_details",
            {
                "booking_id": booking_id,
            },
        )

    if "disruption report" in text:
        return (
            "generate_disruption_report",
            {},
        )

    return None


async def decompose_goal(
    goal: str,
    client: genai.Client,
) -> Plan:

    response = await client.aio.models.generate_content(
        model=MODEL_ID,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"""
{PLANNER_PROMPT}

User goal:
{goal}

Return the plan using the required Plan schema.
"""
                    )
                ],
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Plan,
            temperature=0.1,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty decomposition.")

    data = json.loads(response.text)

    # The user's original goal is authoritative.
    data["goal"] = goal

    return Plan.model_validate(data)


async def execute_plan(
    plan: Plan,
    session: ClientSession,
) -> dict[str, Any]:

    outputs: dict[str, Any] = {}

    for batch in plan.execution_batches():

        async def execute_task(task_id: str) -> tuple[str, Any]:

            task = plan.task(task_id)

            tool_call = task_to_tool_call(task.instruction)

            if tool_call is None:
                return (
                    task_id,
                    {
                        "type": "reasoning_task",
                        "instruction": task.instruction,
                        "dependencies": {
                            dependency: outputs[dependency]
                            for dependency in task.depends_on
                        },
                    },
                )

            tool_name, arguments = tool_call

            result = await call_mcp_tool(
                session,
                tool_name,
                arguments,
            )

            return (
                task_id,
                {
                    "type": "mcp_tool",
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result,
                },
            )

        results = await asyncio.gather(
            *(execute_task(task_id) for task_id in batch)
        )

        for task_id, result in results:
            outputs[task_id] = result

    return outputs


async def synthesize(
    goal: str,
    plan: Plan,
    outputs: dict[str, Any],
    client: genai.Client,
) -> str:

    terminal_tasks = plan.terminal_tasks()

    if len(terminal_tasks) != 1:
        raise ValueError(
            f"Expected exactly one terminal synthesis task, "
            f"found: {terminal_tasks}"
        )

    final_task = plan.task(terminal_tasks[0])

    prompt = f"""
{SYNTHESIS_PROMPT}

Original goal:
{goal}

Final synthesis task:
{final_task.instruction}

Executed plan outputs:
{json.dumps(outputs, indent=2, ensure_ascii=False)}
"""

    response = await client.aio.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
        ),
    )

    result = response.text

    if not result:
        raise RuntimeError("Gemini returned an empty final answer.")

    return result.strip()


async def run_decomposition(goal: str) -> dict[str, Any]:

    client = create_gemini_client()

    async with connect_mcp() as (read_stream, write_stream):

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            init_result = await session.initialize()

            tools_result = await session.list_tools()

            available_tools = [
                tool.name
                for tool in tools_result.tools
            ]

            print("\nMCP connection verified.")
            print("Available tools:", available_tools)

            print("\nGenerating DAG...")

            plan = await decompose_goal(
                goal,
                client,
            )

            print("\nPLAN")
            print("====")
            print(plan.model_dump_json(indent=2))

            print("\nExecution batches:")
            print(plan.execution_batches())

            print("\nExecuting plan...")

            outputs = await execute_plan(
                plan,
                session,
            )

            print("\nGenerating final synthesis...")

            result = await synthesize(
                goal,
                plan,
                outputs,
                client,
            )

            return {
                "goal": goal,
                "plan": plan.model_dump(),
                "execution_batches": plan.execution_batches(),
                "outputs": outputs,
                "result": result,
                "server": {
                    "name": init_result.serverInfo.name,
                    "version": init_result.serverInfo.version,
                },
                "available_tools": available_tools,
                "status": "decomposition and execution completed",
            }


def main() -> None:

    goal = " ".join(sys.argv[1:]).strip()

    if not goal:
        goal = (
            "Generate today's EgyptAir disruption report."
        )

    result = asyncio.run(
        run_decomposition(goal)
    )

    print("\nRESULT")
    print("======")
    print(result["result"])

    print("\nFull execution:")
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()