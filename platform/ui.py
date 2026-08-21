import streamlit as st
import requests

API_URL = "http://localhost:8000/api/admin"

st.set_page_config(page_title="EgyptAir Agent Admin Dashboard", layout="wide")
st.title("EgyptAir Agent Admin Dashboard & Ops Control")

tab1, tab2, tab3 = st.tabs(["MCP Tool Toggles", "RAG Document Management", "HITL Approval Queue"])

# TAB 1: Live Tool Toggles (Guardrail Requirement)
with tab1:
    st.header("MCP Live Tool Enablement Controls")
    st.info("Guardrail Check: Toggling tool states sends an API request directly to update active agent capabilities.")
    
    try:
        res = requests.get(f"{API_URL}/tools").json()
        tools = res.get("tools", {})
        
        for tool, status in tools.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{tool}**")
            with col2:
                new_state = st.toggle("Enable", value=status, key=f"toggle_{tool}")
                if new_state != status:
                    toggle_res = requests.post(
                        f"{API_URL}/tools/toggle", 
                        params={"tool_name": tool, "enabled": new_state}
                    ).json()
                    st.success(f"Updated {tool}: {new_state}")
                    st.rerun()
    except Exception as e:
        st.error(f"Failed to fetch tool capabilities from backend: {e}")

# TAB 2: RAG Document Management

with tab2:
    st.header("RAG Knowledge Base Document Manager")
    
    uploaded_file = st.file_uploader("Upload Policy / Guidance File (PDF/TXT)", type=["pdf", "txt"])
    if uploaded_file is not None:
        if st.button("Index File into Vector Database"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            res = requests.post(f"{API_URL}/rag/upload", files=files).json()
            st.success(f"Successfully uploaded: {res.get('filename')}")
            st.rerun()
            
    st.subheader("Currently Indexed Documents")
    try:
        docs = requests.get(f"{API_URL}/rag/docs").json().get("documents", [])
        for doc in docs:
            st.text(f"• {doc}")
    except Exception as e:
        st.error(f"Error fetching RAG documents: {e}")

# ------------------------------------------------------------------
# TAB 3: Human-In-The-Loop (HITL) Queue
# ------------------------------------------------------------------
with tab3:
    st.header("Pending Human-In-The-Loop (HITL) Authorizations")
    
    try:
        tickets = requests.get(f"{API_URL}/hitl/tickets").json().get("tickets", [])
        for ticket in tickets:
            with st.expander(f"[{ticket['status']}] {ticket['ticket_id']} - {ticket['passenger_name']}"):
                st.write(f"**Requested Action:** {ticket['action']}")
                st.write(f"**Details:** {ticket['details']}")
                
                if ticket["status"] == "PENDING":
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Approve", key=f"app_{ticket['ticket_id']}"):
                            requests.post(f"{API_URL}/hitl/resolve", json={"ticket_id": ticket["ticket_id"], "decision": "APPROVED"})
                            st.success("Approved!")
                            st.rerun()
                    with c2:
                        if st.button("Reject", key=f"rej_{ticket['ticket_id']}"):
                            requests.post(f"{API_URL}/hitl/resolve", json={"ticket_id": ticket["ticket_id"], "decision": "REJECTED"})
                            st.warning("Rejected!")
                            st.rerun()
    except Exception as e:
        st.error(f"Error fetching tickets: {e}")