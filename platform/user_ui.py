import streamlit as st
import requests

API_URL = "http://localhost:8000/api/chat"

st.set_page_config(page_title="EgyptAir Passenger Assistant", layout="centered")
st.title("EgyptAir Customer Assistant")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------------------------------------------------------
# Guardrail Check: Agent Selector Dropdown
# Allows switching between State-Graph and Legacy/Planning agents
# ------------------------------------------------------------------
st.sidebar.header("Agent Settings")
selected_agent = st.sidebar.selectbox(
    "Select Agent Architecture:",
    options=["state_graph", "legacy_planning"],
    format_func=lambda x: "State-Graph Agent (LangGraph)" if x == "state_graph" else "Legacy Agent (Memory / RAG / Planning)"
)

st.sidebar.info(
    f"Currently chatting with: **{selected_agent}**\n\n"
    "Queries will be dispatched directly to the selected pipeline."
)

# Render existing conversation history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Chat Input
if prompt := st.chat_input("Ask about flights, baggage, or seat reservations..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call backend API with selected agent guardrail flag
    with st.chat_message("assistant"):
        with st.spinner(f"Processing query via {selected_agent}..."):
            try:
                res = requests.post(
                    API_URL,
                    json={"prompt": prompt, "agent_type": selected_agent}
                ).json()
                
                reply = res.get("response", "Error processing request.")
                st.markdown(reply)
                
                # Save assistant response
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                error_msg = f"Connection Error: Ensure backend (`platform/api.py`) is running. ({e})"
                st.error(error_msg)