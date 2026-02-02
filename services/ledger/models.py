"""Data models for ledger service."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal


class Event(BaseModel):
    """Instruction event stored in ledger."""
    schema_version: str = "1.0"
    event_id: str = Field(..., description="Unique event identifier")
    session_id: str = Field(..., description="Session identifier")
    ts: datetime = Field(default_factory=datetime.now)
    source: Literal["system", "developer", "user", "memory", "claude_md", "skill", "tool_output", "agent_internal"]
    scope: Literal["global", "conversation", "task", "step", "file"]
    text: str = Field(..., description="Raw instruction text")
    metadata: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "schema_version": "1.0",
                "event_id": "evt_abc123",
                "session_id": "session_xyz789",
                "ts": "2026-02-02T10:00:00Z",
                "source": "user",
                "scope": "global",
                "text": "Never modify production files",
                "metadata": {}
            }
        }


class EventCreate(BaseModel):
    """Request model for creating events."""
    session_id: str = Field(..., description="Session identifier")
    source: Literal["system", "developer", "user", "memory", "claude_md", "skill", "tool_output", "agent_internal"]
    scope: Literal["global", "conversation", "task", "step", "file"]
    text: str = Field(..., description="Raw instruction text")
    metadata: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_xyz789",
                "source": "user",
                "scope": "global",
                "text": "Never modify production files",
                "metadata": {}
            }
        }
