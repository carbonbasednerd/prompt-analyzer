"""Ledger service - Append-only instruction event storage."""
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import uuid
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
import asyncio

from .models import Event, EventCreate
from .storage import LedgerStorage

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

app = FastAPI(
    title="Prompt Analyzer - Ledger Service",
    description="Append-only instruction event storage",
    version="0.1.0",
)

# Initialize storage
data_dir = Path(os.getenv("DATA_DIR", "/data/ledger"))
storage = LedgerStorage(data_dir)

# For SSE streaming
event_subscribers = []


def generate_id() -> str:
    """Generate unique event ID."""
    return f"evt_{uuid.uuid4().hex[:12]}"


@app.post("/ledger/append", response_model=Event)
async def append_event(event_data: EventCreate):
    """Append new instruction event to ledger."""
    try:
        event = Event(
            event_id=generate_id(),
            ts=datetime.now(),
            **event_data.model_dump()
        )

        storage.append_event(event)

        logger.info(
            "event_appended",
            event_id=event.event_id,
            session_id=event.session_id,
            source=event.source,
            text_length=len(event.text)
        )

        # Notify SSE subscribers
        for queue in event_subscribers:
            await queue.put(event)

        return event

    except Exception as e:
        logger.error("append_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ledger/session/{session_id}", response_model=list[Event])
def get_session(session_id: str):
    """Get all events for a session."""
    try:
        events = storage.get_session_events(session_id)
        return events
    except Exception as e:
        logger.error("get_session_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ledger/events")
def get_events(start: Optional[str] = None, end: Optional[str] = None):
    """Get events within a time range."""
    try:
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None

        events = storage.get_events_range(start_dt, end_dt)
        return events
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {e}")
    except Exception as e:
        logger.error("get_events_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ledger/sessions")
def list_sessions():
    """List all session IDs."""
    try:
        sessions = storage.list_sessions()
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        logger.error("list_sessions_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ledger/stream")
async def stream_events(session_id: Optional[str] = None):
    """Server-Sent Events endpoint for real-time updates."""
    async def event_generator():
        queue = asyncio.Queue()
        event_subscribers.append(queue)

        try:
            while True:
                event = await queue.get()

                # Filter by session if requested
                if session_id and event.session_id != session_id:
                    continue

                yield {
                    "event": "new_event",
                    "data": event.model_dump_json()
                }
        except asyncio.CancelledError:
            event_subscribers.remove(queue)

    return EventSourceResponse(event_generator())


@app.get("/health")
def health():
    """Health check endpoint."""
    try:
        # Basic health check - verify data directory exists
        if not data_dir.exists():
            raise Exception("Data directory not found")

        return {
            "status": "healthy",
            "service": "ledger",
            "data_dir": str(data_dir),
            "sessions": len(storage.list_sessions())
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
