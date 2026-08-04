""""Purpose

This file defines all data structures used by the memory system.

Notice something important:

These classes do not perform any work.

They only describe data.

That's exactly how Pydantic models should be used."""
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


# ==========================================================
# Conversation Message
# ==========================================================

class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==========================================================
# Scratchpad
# ==========================================================

class ScratchpadState(BaseModel):
    current_goal: Optional[str] = None
    current_plan: Optional[str] = None
    current_tool: Optional[str] = None
    intermediate_state: Optional[str] = None


# ==========================================================
# Router Decision
# ==========================================================

class RoutingDecision(BaseModel):
    reasoning: str
    destination: Literal["forget", "episodic"]

    event_summary: Optional[str] = None
    context: Optional[str] = None
    outcome: Optional[str] = None

    entity_id: Optional[str] = None


# ==========================================================
# Episodic Memory
# ==========================================================

class Episode(BaseModel):

    episode_id: Optional[int] = None

    entity_id: Optional[str] = None

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    event_summary: str

    context: str

    outcome: str

    conversation_id: Optional[str] = None


# ==========================================================
# Semantic Fact
# ==========================================================

class SemanticFact(BaseModel):

    fact_id: Optional[int] = None

    entity_id: str

    attribute: str

    value: str

    version: int = 1

    current: bool = True

    status: str = "ACTIVE"

    expires_at: Optional[datetime] = None

    updated_from_episode: Optional[int] = None