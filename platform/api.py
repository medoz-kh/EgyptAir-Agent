import os
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

app = FastAPI(title="EgyptAir Platform Admin API")

# Memory store for dynamic tool toggles (MCP sync)
ACTIVE_TOOLS: Dict[str, bool] = {
    "flight_status_search": True,
    "sqlite_seat_reservation": True,
    "baggage_policy_lookup": True,
}

# Pending Human-In-The-Loop (HITL) Queue
PENDING_TICKETS: List[Dict[str, Any]] = [
    {
        "ticket_id": "TCK-8901",
        "passenger_name": "Bob Vance",
        "action": "Overbooking Exception Request",
        "details": "Requesting double-seat allocation on MS702 (Row 12).",
        "status": "PENDING"
    }
]

# RAG Document Storage Mock
STORED_DOCUMENTS: List[str] = ["egyptair_baggage_policy_2026.pdf"]

# --- Task 3.1.2: Tool Toggles (MCP Integration Endpoint) ---
@app.get("/api/admin/tools")
def get_tools():
    """Returns live tool enablement state."""
    return {"tools": ACTIVE_TOOLS}

@app.post("/api/admin/tools/toggle")
def toggle_tool(tool_name: str, enabled: bool):
    """Dynamically enables/disables tools in active agent registry."""
    if tool_name not in ACTIVE_TOOLS:
        raise HTTPException(status_code=404, detail="Tool not registered in MCP capability map.")
    
    ACTIVE_TOOLS[tool_name] = enabled
    return {
        "status": "SUCCESS",
        "tool": tool_name,
        "active": enabled,
        "message": f"MCP capability '{tool_name}' updated live to {enabled}."
    }

# --- Task 3.1.1: RAG Document Management ---
@app.get("/api/admin/rag/docs")
def list_documents():
    return {"documents": STORED_DOCUMENTS}

@app.post("/api/admin/rag/upload")
async def upload_document(file: UploadFile = File(...)):
    STORED_DOCUMENTS.append(file.filename)
    return {"status": "SUCCESS", "filename": file.filename, "message": "Document indexed into vector store."}

# --- Task 3.1.1: HITL Ticket Approval Queue ---
@app.get("/api/admin/hitl/tickets")
def get_pending_tickets():
    return {"tickets": PENDING_TICKETS}

class TicketAction(BaseModel):
    ticket_id: str
    decision: str  # "APPROVED" or "REJECTED"

@app.post("/api/admin/hitl/resolve")
def resolve_ticket(action: TicketAction):
    for ticket in PENDING_TICKETS:
        if ticket["ticket_id"] == action.ticket_id:
            ticket["status"] = action.decision
            return {"status": "SUCCESS", "ticket_id": action.ticket_id, "new_status": action.decision}
    raise HTTPException(status_code=404, detail="Ticket ID not found.")

class ChatRequest(BaseModel):
    prompt: str
    agent_type: str  # "state_graph" or "legacy_planning"

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Guardrail Check: Routes requests between State-Graph agents
    and Legacy Memory/RAG/Planning agents based on UI selection.
    """
    if req.agent_type == "state_graph":
        # Dispatch to State-Graph / LangGraph Agent Workflow
        response_text = f"[State-Graph Agent Executed]: Processed '{req.prompt}' using graph state transitions."
    elif req.agent_type == "legacy_planning":
        # Dispatch to Legacy Memory/RAG/Planning Router (PS, ToT, LATS)
        response_text = f"[Legacy Planning Agent Executed]: Processed '{req.prompt}' using Plan-and-Solve / ToT logic."
    else:
        raise HTTPException(status_code=400, detail="Invalid agent type selected.")

    return {
        "status": "SUCCESS",
        "agent_used": req.agent_type,
        "response": response_text
    }