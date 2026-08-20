"""
agent/agent_llm.py -- application entrypoint (project brief section 14).

Responsibility: ASSEMBLE the real systems and hand control to StateGraph.
This file does NOT reason about flights, compensation, or policy -- it has
no business logic of its own. It:

    1. Loads environment variables.
    2. Creates the Gemini client.
    3/4. Starts the real MCP stdio connection + ClientSession (registers
         a sampling_callback for the server's sampling requests AND an
         elicitation_callback for approve_compensation's ctx.elicit()
         manager-confirmation prompt).
    5. Initializes RAG (VectorStoreManager + HybridRAGSearch), seeded from
       the real sql://policies MCP resource.
    6. Initializes memory (mcp_server.memory.manger.MemoryManager).
    7. Builds GraphDependencies (state_graph.runtime).
    8. Builds all three compiled workflows (state_graph.workflows), sharing
       one checkpointer so HITL survives across turns within this process.
    9-11. REPL loop: read a request, select a workflow (via the technique
         engine -- see technique_engine.select_workflow), build initial
         AgentState, invoke the graph.
    13. If the graph interrupts (compensation HITL), prompt for a real
        human decision and resume the SAME thread with Command(resume=...).
    14. Print the final result.
    15. Update memory.

This intentionally does NOT reimplement the old Gemini function-call loop.
See agent/agent_llm_legacy_direct_loop.py for that (kept for reference
only, not used here) -- StateGraph is the single workflow orchestrator.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from google import genai

from mcp import ClientSession, StdioServerParameters
import mcp.types as mcp_types
from mcp.client.stdio import stdio_client

from langgraph.types import Command

from mcp_server.memory.manger import MemoryManager
from rag.hybrid_rag import HybridRAGSearch
from rag.self_rag import GroundingGuardrail
from rag.vector_store import VectorStoreManager

from state_graph import persistence, runtime, workflows as workflows_module
from state_graph.state import new_state
from state_graph.technique_engine import DEFAULT_MODEL_ID

load_dotenv()

MODEL_ID = os.getenv("GEMINI_MODEL_ID", DEFAULT_MODEL_ID)
MCP_SERVER_PATH = "mcp_server/server.py"

# Demo actor identity, standing in for an authenticated session.
# A real deployment sources these from auth, not constants -- flagged
# here rather than hidden, since it's the one thing this file has to
# invent to call the real authorized MCP tools.
DEMO_EMPLOYEE_ID = int(os.getenv("DEMO_EMPLOYEE_ID", "1"))
DEMO_MANAGER_ID = int(os.getenv("DEMO_MANAGER_ID", "2"))


async def sampling_handler(context, request: mcp_types.CreateMessageRequestParams):
    """Answers the MCP server's own sampling requests (unchanged from the
    prior implementation -- this is MCP protocol plumbing, not agent
    reasoning, so it stays here rather than in state_graph/)."""
    genai_client: genai.Client = context.session._egyptair_genai_client  # set below
    prompt_text = ""
    for msg in request.messages:
        if hasattr(msg.content, "text"):
            prompt_text += msg.content.text + "\n"

    response = await genai_client.aio.models.generate_content(
        model=MODEL_ID,
        contents=prompt_text,
        config={
            "system_instruction": request.systemPrompt or "You are an AI assistant helping an MCP server.",
            "max_output_tokens": request.maxTokens or 350,
        },
    )
    return mcp_types.CreateMessageResult(
        role="assistant",
        content=mcp_types.TextContent(type="text", text=response.text or ""),
        model=MODEL_ID,
    )


async def elicitation_handler(context, params: mcp_types.ElicitRequestParams) -> mcp_types.ElicitResult:
    """
    Answers approve_compensation's ctx.elicit(response_type=bool) call
    (compensation_tools.py). This is a SEPARATE human-in-the-loop gate
    from the StateGraph human_approval interrupt: the graph-level
    interrupt decides whether the customer-service workflow proceeds to
    submit a request at all; THIS gate is the manager's own confirmation
    inside the MCP tool itself when it finalizes that request.

    NOTE: the exact `content` key(s) expected on ElicitResult depend on
    the installed mcp/fastmcp SDK version's boolean elicitation schema
    (not something visible from the repo files alone) -- verify this
    against `pip show mcp fastmcp` in your environment; {"value": bool}
    is the common convention but confirm before relying on it in prod.
    """
    print(f"\n🖐️  [MCP ELICITATION] {params.message}")
    answer = input("Confirm? [y/n]: ").strip().lower()
    accepted = answer in ("y", "yes")
    return mcp_types.ElicitResult(action="accept", content={"value": accepted})


async def seed_and_build_rag(session: ClientSession):
    """Seeds the vector store from the real sql://policies resource, same
    as the legacy loop did -- unchanged behavior, just relocated."""
    vector_store = VectorStoreManager()
    hybrid_rag = HybridRAGSearch(vector_store)

    policy_resource = await session.read_resource("sql://policies")
    policy_text = policy_resource.contents[0].text
    try:
        policies_data = json.loads(policy_text)
        if isinstance(policies_data, list) and policies_data:
            vector_store.add_documents(
                documents=[p["content"] for p in policies_data],
                metadatas=[{"policy_id": p["policy_id"], "title": p["title"]} for p in policies_data],
                ids=[f"policy_{p['policy_id']}" for p in policies_data],
            )
            print("✅ Seeded Vector Store with EgyptAir Policies!")
    except Exception as e:
        print(f"⚠️  Vector Store Seeding Note: {e}")

    return vector_store, hybrid_rag


def print_interrupt(payload: dict) -> None:
    print("\n⏸️  [HUMAN APPROVAL REQUIRED]")
    print(f"    Booking:          {payload.get('booking_id')}")
    print(f"    Proposed amount:  {payload.get('proposed_amount')} {payload.get('currency')}")
    print(f"    Policy-capped:    {payload.get('policy_capped_amount')}")
    print(f"    Within policy:    {payload.get('within_policy')}")
    print(f"    Reason:           {payload.get('reason')}")


async def run():
    genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    server_params = StdioServerParameters(
        command=sys.executable, args=[MCP_SERVER_PATH], env=dict(os.environ)
    )

    print(f"🔌 Connecting to MCP Server at '{MCP_SERVER_PATH}'...")
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            sampling_callback=sampling_handler,
            elicitation_callback=elicitation_handler,
        ) as session:
            session._egyptair_genai_client = genai_client  # used by sampling_handler above

            init_result = await session.initialize()
            print(f"🤝 Connected to {init_result.serverInfo.name} {init_result.serverInfo.version}")

            vector_store, hybrid_rag = await seed_and_build_rag(session)
            guardrail = GroundingGuardrail(
                search_tool=hybrid_rag.search, genai_client=genai_client, model_id=MODEL_ID
            )
            memory = MemoryManager()

            deps = runtime.build_graph_dependencies(
                session=session,
                genai_client=genai_client,
                hybrid_rag=hybrid_rag,
                guardrail=guardrail,
                memory=memory,
                model_id=MODEL_ID,
            )
            checkpointer = persistence.get_checkpointer("memory")
            graphs = workflows_module.build_all_workflows(deps, checkpointer)

            print("\n✨ EgyptAir Autonomous Agent ready (StateGraph orchestration).")
            print("   Workflows: flight_investigation | compensation | full_disruption\n")

            while True:
                user_input = input("\nUser > ").strip()
                if user_input.lower() in ("exit", "quit"):
                    print("\nRunning Memory Consolidation...\n")
                    memory.consolidate()
                    break
                if not user_input:
                    continue

                memory.add_turn(role="user", content=user_input)
                memory.update_goal("Assist the passenger with their request.")

                workflow_name = await deps.technique.select_workflow(user_input)
                graph = graphs[workflow_name]
                thread_id = persistence.new_thread_id(workflow_name)
                config = {"configurable": {"thread_id": thread_id}}

                state = new_state(
                    request_id=thread_id,
                    user_request=user_input,
                    workflow=workflow_name,
                    employee_id=DEMO_EMPLOYEE_ID,
                    manager_id=DEMO_MANAGER_ID,
                )

                print(f"\n🧭 Workflow selected: {workflow_name}")
                deps.memory.update_tool(f"state_graph:{workflow_name}")
                result = await graph.ainvoke(state, config=config)

                if "__interrupt__" in result:
                    interrupt_obj = result["__interrupt__"][0]
                    print_interrupt(interrupt_obj.value)
                    decision = input("Approve compensation? [approve/reject]: ").strip().lower()
                    resume_payload = {
                        "decision": "approve" if decision.startswith("a") else "reject",
                        "employee_id": DEMO_EMPLOYEE_ID,
                        "manager_id": DEMO_MANAGER_ID,
                    }
                    result = await graph.ainvoke(Command(resume=resume_payload), config=config)

                final_message = result.get("final_message", "(no final message)")
                print(f"\nAgent > {final_message}")

                memory.add_turn(role="assistant", content=final_message)
                memory.update_intermediate_state(f"workflow={workflow_name} complete")


if __name__ == "__main__":
    asyncio.run(run())
