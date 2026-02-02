"""Data models for extractor service."""
from pydantic import BaseModel, Field, validator
from typing import Literal


class Claim(BaseModel):
    """Semantic claim extracted from instruction."""
    schema_version: str = "1.0"
    claim_id: str = Field(..., description="Unique claim identifier")
    session_id: str = Field(..., description="Session identifier")
    event_id: str = Field(..., description="Source event identifier")
    modality: Literal["must", "must_not", "should", "prefer", "avoid", "allowed"]
    action: str = Field(..., description="Action being constrained")
    target: str = Field(..., description="Target of the action")
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(..., description="Verbatim quotes from text")

    @validator('evidence')
    def evidence_not_empty(cls, v):
        if not v:
            raise ValueError("Evidence must contain at least one quote")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "schema_version": "1.0",
                "claim_id": "clm_abc123",
                "session_id": "session_xyz789",
                "event_id": "evt_def456",
                "modality": "must_not",
                "action": "file_write",
                "target": "production files",
                "conditions": [],
                "exceptions": [],
                "confidence": 0.95,
                "evidence": ["Never modify production files"]
            }
        }


class ExtractionRequest(BaseModel):
    """Request model for claim extraction."""
    event_id: str
    session_id: str
    text: str

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_def456",
                "session_id": "session_xyz789",
                "text": "Never modify production files"
            }
        }


class ExtractionResponse(BaseModel):
    """Response model for claim extraction."""
    event_id: str
    claims: list[Claim]
    extraction_time_ms: float
