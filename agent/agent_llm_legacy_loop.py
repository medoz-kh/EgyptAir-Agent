"""
agent_llm_legacy_direct_loop.py

** NOT the production entrypoint. **

This is the original Gemini-function-call direct loop (Gemini -> function
call -> MCP -> Gemini final answer), preserved here unmodified because
the project brief explicitly says this pattern "must NOT become a second
orchestration architecture for workflow requests" -- it's kept for
reference / free-text policy Q&A experimentation only, not deleted
outright. The real entrypoint is agent/agent_llm.py, which builds
GraphDependencies and lets state_graph/ (LangGraph StateGraph) drive
workflow execution instead of this loop.
"""

import asyncio
import os
from rag.vector_store import VectorStoreManager
from rag.hybrid_rag import HybridRAGSearch
from rag.self_rag import SelfRAGVerifier, GroundingGuardrail
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp_server.memory.manger import MemoryManager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import mcp.types as mcp_types
import sys
import json
import copy

load_dotenv()

MODEL_ID = "gemini-3.1-flash-lite"  

def clean_schema(schema_dict: dict) -> dict:
    """
    Removes fields incompatible with Gemini API function declarations.
    """
    if not isinstance(schema_dict, dict):
        return schema_dict

    cleaned = copy.deepcopy(schema_dict)
    cleaned.pop("additionalProperties", None)
    cleaned.pop("additional_properties", None)
    cleaned.pop("$schema", None)

    if "properties" in cleaned and isinstance(cleaned["properties"], dict):
        for prop_name, prop_val in cleaned["properties"].items():
            if isinstance(prop_val, dict):
                cleaned["properties"][prop_name] = clean_schema(prop_val)

    return cleaned


class MCPGeminiClient:
    def __init__(self, server_script_path: str):
        self.server_script_path = server_script_path
        self.genai_client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )

    async def sampling_handler(self, context, request: mcp_types.CreateMessageRequestParams):
        print("\n📬 [SAMPLING REQUEST RECEIVED FROM MCP SERVER]")
        prompt_text = ""
        for msg in request.messages:
            if hasattr(msg.content, "text"):
                prompt_text += msg.content.text + "\n"
            elif isinstance(msg.content, dict) and msg.content.get("type") == "text":
                prompt_text += msg.content.get("text", "") + "\n"

        system_instruction = (
            request.systemPrompt or "You are an AI assistant helping an MCP server."
        )

        response = await self.genai_client.aio.models.generate_content(
            model=MODEL_ID,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=request.maxTokens or 350
            )
        )

        generated_text = response.text or ""
        return mcp_types.CreateMessageResult(
            role="assistant",
            content=mcp_types.TextContent(
                type="text",
                text=generated_text
            ),
            model=MODEL_ID
        )

    async def run(self):
        server_params = StdioServerParameters(
            command=sys.executable,  
            args=[self.server_script_path],
            env=dict(os.environ)  
        )

        print(f"🔌 Connecting to MCP Server at '{self.server_script_path}'...")

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream,
                write_stream,
                sampling_callback=self.sampling_handler
            ) as session:

                print("\n🤝 Initializing MCP Session...")
                init_result = await session.initialize()
                print(f"Connected to {init_result.serverInfo.name} {init_result.serverInfo.version}")

                mcp_tools = await session.list_tools()
                function_declarations = []

                for tool in mcp_tools.tools:
                    cleaned_params = clean_schema(tool.inputSchema)
                    function_declarations.append(
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": cleaned_params,
                        }
                    )

                policy_resource = await session.read_resource("sql://policies")
                policy_text = policy_resource.contents[0].text

                # ====================================================
                # Initialize RAG, Vector Store & Guardrails
                # ====================================================
                vector_store = VectorStoreManager()
                hybrid_rag = HybridRAGSearch(vector_store)
                self_rag = SelfRAGVerifier(self.genai_client)
                
                # NEW: Instantiate Option B Grounding Guardrail
                guardrail = GroundingGuardrail(
                    search_tool=hybrid_rag.search,
                    genai_client=self.genai_client,
                    model_id=MODEL_ID
                )

                # Seed ChromaDB with policies from the database
                try:
                    policies_data = json.loads(policy_text)
                    if isinstance(policies_data, list):
                        docs = [p["content"] for p in policies_data]
                        metas = [
                            {"policy_id": p["policy_id"], "title": p["title"]}
                            for p in policies_data
                        ]
                        ids = [f"policy_{p['policy_id']}" for p in policies_data]
                        
                        vector_store.add_documents(
                            documents=docs,
                            metadatas=metas,
                            ids=ids
                        )
                        print("✅ Seeded Vector Store with EgyptAir Policies!")
                except Exception as e:
                    print(f"⚠️ Vector Store Seeding Note: {e}")

                system_instruction = (
                    "You are an EgyptAir customer service assistant.\n"
                    "Use the provided official EgyptAir policy context when answering passengers.\n"
                    "Do not make up facts outside the retrieved policy details."
                )

                gemini_tools = [
                    types.Tool(function_declarations=function_declarations)
                ] if function_declarations else []

                print("\n✨ Gemini MCP Client & Grounded RAG Engine Ready!")

                chat_history = []
                memory = MemoryManager()

                while True:
                    user_input = input("\nUser > ").strip()

                    if user_input.lower() in ["exit", "quit"]:
                        print("\nRunning Memory Consolidation...\n")
                        memory.consolidate()
                        break

                    if not user_input:
                        continue

                    memory.add_turn(role="user", content=user_input)
                    memory.update_goal("Assist the passenger with their request.")

                    chat_history.append(
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=user_input)]
                        )
                    )

                    # ---------------------------------------
                    # Ask Gemini to route (Tool vs Normal Chat)
                    # ---------------------------------------
                    response = await self.genai_client.aio.models.generate_content(
                        model=MODEL_ID,
                        contents=chat_history,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=gemini_tools
                        )
                    )

                    # ==========================================
                    # Route A: Gemini wants to call an MCP Tool
                    # ==========================================
                    if response.function_calls:
                        for function_call in response.function_calls:
                            tool_name = function_call.name
                            tool_args = dict(function_call.args)

                            print(f"\n🤖 Gemini requested MCP tool '{tool_name}'")
                            print(f"Arguments: {tool_args}")

                            memory.update_tool(tool_name)
                            memory.update_intermediate_state("Executing MCP Tool")

                            tool_result = await session.call_tool(
                                name=tool_name,
                                arguments=tool_args
                            )

                            tool_output_text = "\n".join(
                                c.text for c in tool_result.content if c.type == "text"
                            )

                            print(f"\n⚙ Tool Output:\n{tool_output_text}")

                            chat_history.append(response.candidates[0].content)
                            chat_history.append(
                                types.Content(
                                    role="user",
                                    parts=[
                                        types.Part.from_function_response(
                                            name=tool_name,
                                            response={"result": tool_output_text}
                                        )
                                    ]
                                )
                            )

                            final_response = await self.genai_client.aio.models.generate_content(
                                model=MODEL_ID,
                                contents=chat_history,
                                config=types.GenerateContentConfig(tools=gemini_tools)
                            )

                            assistant_text = final_response.text or ""
                            print(f"\nGemini > {assistant_text}")

                            memory.add_turn(role="assistant", content=assistant_text)
                            memory.update_intermediate_state("Tool execution completed.")
                            chat_history.append(final_response.candidates[0].content)

                    # ==========================================
                    # Route B: Normal Conversation / Grounded RAG
                    # ==========================================
                    else:
                        print("\n🛡️ [GUARDRAIL CHECK] Ensuring answer is fully grounded in EgyptAir policy...")
                        
                        # Use Option B to generate, critique, and retry the policy answer
                        assistant_text = await guardrail.answer_with_grounding_check(user_input, top_k=3)

                        print(f"\nGemini > {assistant_text}")

                        memory.add_turn(role="assistant", content=assistant_text)
                        
                        # Replace the raw un-grounded response with the safely grounded one in history
                        chat_history.append(
                            types.Content(
                                role="model",
                                parts=[types.Part.from_text(text=assistant_text)]
                            )
                        )

if __name__ == "__main__":
    client = MCPGeminiClient(server_script_path="mcp_server/server.py")
    asyncio.run(client.run())