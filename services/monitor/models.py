"""Data models for monitor service."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class Claim(BaseModel):
    """Semantic claim (mirror of extractor model)."""
    schema_version: str = "1.0"
    claim_id: str
    session_id: str
    event_id: str
    modality: Literal["must", "must_not", "should", "prefer", "avoid", "allowed"]
    action: str
    target: str
    conditions: list[str] = []
    exceptions: list[str] = []
    confidence: float
    evidence: list[str]


class Conflict(BaseModel):
    """Detected contradiction between claims."""
    schema_version: str = "1.0"
    conflict_id: str = Field(..., description="Unique conflict identifier")
    session_id: str = Field(..., description="Session identifier")
    claims: list[str] = Field(..., description="Claim IDs involved in this conflict")
    severity: Literal["hard", "soft", "scope", "style"]
    explanation: str = Field(..., description="Human-readable explanation")
    confidence: float = Field(..., ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "example": {
                "schema_version": "1.0",
                "conflict_id": "cfl_abc123",
                "session_id": "session_xyz789",
                "claims": ["clm_def456", "clm_ghi789"],
                "severity": "hard",
                "explanation": "Contradictory instructions: must_not file_write vs must file_write on 'production files'",
                "confidence": 0.95
            }
        }


class ProcessingState(str, Enum):
    """Event processing state."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EventProcessingLog(BaseModel):
    """Processing log entry for error recovery."""
    event_id: str
    session_id: str
    state: ProcessingState
    attempts: int = 0
    last_error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    claims_extracted: int = 0
