import asyncio
import os
from rag.vector_store import VectorStoreManager
from rag.hybrid_rag import HybridRAGSearch
from rag.self_rag import SelfRAGVerifier
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

    async def sampling_handler(
        self,
        context,
        request: mcp_types.CreateMessageRequestParams
    ):

        print("\n📬 [SAMPLING REQUEST RECEIVED FROM MCP SERVER]")

        prompt_text = ""

        for msg in request.messages:

            if hasattr(msg.content, "text"):

                prompt_text += msg.content.text + "\n"

            elif (
                isinstance(msg.content, dict)
                and msg.content.get("type") == "text"
            ):

                prompt_text += msg.content.get("text", "") + "\n"

        system_instruction = (
            request.systemPrompt
            or
            "You are an AI assistant helping an MCP server."
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
            command=sys.executable,  # Forces MCP server to use the active .venv Python
            args=[self.server_script_path],
            env=dict(os.environ)  # Passes environment variables to the server
        )

        print(
            f"🔌 Connecting to MCP Server at "
            f"'{self.server_script_path}'..."
        )

        async with stdio_client(server_params) as (

            read_stream,

            write_stream

        ):

            async with ClientSession(

                read_stream,

                write_stream,

                sampling_callback=self.sampling_handler

            ) as session:

                print("\n🤝 Initializing MCP Session...")

                init_result = await session.initialize()

                print(
                    f"Connected to "
                    f"{init_result.serverInfo.name} "
                    f"{init_result.serverInfo.version}"
                )

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

                policy_resource = await session.read_resource(
                    "sql://policies"
                )

                policy_text = policy_resource.contents[0].text

                # ====================================================
                # NEW: Initialize RAG & Seed Vector Store
                # ====================================================
                vector_store = VectorStoreManager()
                hybrid_rag = HybridRAGSearch(vector_store)
                self_rag = SelfRAGVerifier(self.genai_client)

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
                        
                        # Add to vector database
                        vector_store.add_documents(
                            documents=docs,
                            metadatas=metas,
                            ids=ids
                        )
                        print("✅ Seeded Vector Store with EgyptAir Policies!")
                except Exception as e:
                    print(f"⚠️ Vector Store Seeding Note: {e}")

                # System instruction base prompt
                system_instruction = (
                    "You are an EgyptAir customer service assistant.\n"
                    "Use the provided official EgyptAir policy context when answering passengers.\n"
                    "Do not make up facts outside the retrieved policy details."
                )

                gemini_tools = [
                    types.Tool(
                        function_declarations=function_declarations
                    )
                ] if function_declarations else []

                print("\n✨ Gemini MCP Client & RAG Engine Ready!")

                # ==========================
                # Gemini & Memory Initialization
                # ==========================
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

                    # ====================================================
                    # NEW: Perform Hybrid RAG Search for User Query
                    # ====================================================
                    retrieved_chunks = hybrid_rag.search(
                        query=user_input,
                        n_results=3
                    )

                    context_text = ""
                    for chunk in retrieved_chunks:
                        # Check relevance using Self-RAG
                        is_relevant = await self_rag.verify_relevance(
                            query=user_input,
                            retrieved_chunk=chunk["content"]
                        )
                        if is_relevant:
                            context_text += f"\n- Policy Title: {chunk['metadata'].get('title', 'N/A')}\n  Details: {chunk['content']}\n"

                    # Combine user input with retrieved grounded context
                    augmented_user_input = (
                        f"{user_input}\n\n"
                        f"[RETRIEVED EGYPTAIR POLICIES CONTEXT]:\n{context_text if context_text else 'No specific policy chunk retrieved.'}"
                    )

                    # ---------------------------------------
                    # Memory (User Message)
                    # ---------------------------------------
                    memory.add_turn(role="user", content=user_input)
                    memory.update_goal("Assist the passenger with their request.")

                    # ---------------------------------------
                    # Gemini Chat History
                    # ---------------------------------------
                    # We pass the augmented input (with RAG context) to Gemini, 
                    # but we only added the raw user_input to the semantic memory above.
                    chat_history.append(
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=augmented_user_input)]
                        )
                    )

                    # ---------------------------------------
                    # Ask Gemini
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
                    # Gemini wants to call an MCP Tool
                    # ==========================================

                    if response.function_calls:

                        for function_call in response.function_calls:

                            tool_name = function_call.name

                            tool_args = dict(function_call.args)

                            print(
                                f"\n🤖 Gemini requested MCP tool "
                                f"'{tool_name}'"
                            )

                            print(
                                f"Arguments: {tool_args}"
                            )

                            # -----------------------------------
                            # Scratchpad
                            # -----------------------------------

                            memory.update_tool(tool_name)

                            memory.update_intermediate_state(
                                "Executing MCP Tool"
                            )

                            # -----------------------------------
                            # Execute MCP Tool
                            # -----------------------------------

                            tool_result = await session.call_tool(
                                name=tool_name,
                                arguments=tool_args
                            )

                            tool_output_text = "\n".join(

                                c.text

                                for c in tool_result.content

                                if c.type == "text"

                            )

                            print(
                                f"\n⚙ Tool Output:\n"
                                f"{tool_output_text}"
                            )

                            # -----------------------------------
                            # Add Tool Call
                            # -----------------------------------

                            chat_history.append(
                                response.candidates[0].content
                            )

                            chat_history.append(

                                types.Content(

                                    role="user",

                                    parts=[

                                        types.Part.from_function_response(

                                            name=tool_name,

                                            response={
                                                "result": tool_output_text
                                            }
                                        )

                                    ]
                                )
                            )

                            # -----------------------------------
                            # Final Gemini Response
                            # -----------------------------------

                            final_response = await self.genai_client.aio.models.generate_content(

                                model=MODEL_ID,

                                contents=chat_history,

                                config=types.GenerateContentConfig(

                                    tools=gemini_tools

                                )
                            )

                            assistant_text = final_response.text or ""

                            print(f"\nGemini > {assistant_text}")

                            # -----------------------------------
                            # Memory (Assistant Message)
                            # -----------------------------------

                            memory.add_turn(

                                role="assistant",

                                content=assistant_text

                            )

                            memory.update_intermediate_state(

                                "Tool execution completed."

                            )

                            chat_history.append(

                                final_response.candidates[0].content

                            )

                    # ==========================================
                    # Normal Conversation
                    # ==========================================

                    else:

                        assistant_text = response.text or ""

                        print(f"\nGemini > {assistant_text}")

                        memory.add_turn(

                            role="assistant",

                            content=assistant_text

                        )

                        chat_history.append(

                            response.candidates[0].content

                        )


if __name__ == "__main__":
    client = MCPGeminiClient(
        server_script_path="mcp_server/server.py"
    )

    asyncio.run(client.run())