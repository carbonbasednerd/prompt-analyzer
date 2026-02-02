"""Monitor service - Pipeline orchestration and conflict detection."""
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
import structlog
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from .models import Claim, Conflict, ProcessingState, EventProcessingLog
from .detector import detect_conflicts

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
    title="Prompt Analyzer - Monitor Service",
    description="Pipeline orchestration and conflict detection",
    version="0.1.0",
)

# Configuration
LEDGER_URL = os.getenv("LEDGER_URL", "http://ledger:8000")
EXTRACTOR_URL = os.getenv("EXTRACTOR_URL", "http://extractor:8000")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

# Data directories
CLAIMS_DIR = DATA_DIR / "claims"
CONFLICTS_DIR = DATA_DIR / "conflicts"
STATE_DIR = DATA_DIR / "monitor"

# Create directories
CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
CONFLICTS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Processing state
processed_events = set()
processing_log_path = STATE_DIR / "processing_log.jsonl"


def load_processed_events():
    """Load list of already processed events."""
    global processed_events
    if processing_log_path.exists():
        with open(processing_log_path, "r") as f:
            for line in f:
                try:
                    log = EventProcessingLog(**json.loads(line))
                    if log.state == ProcessingState.COMPLETED:
                        processed_events.add(log.event_id)
                except (json.JSONDecodeError, ValueError):
                    continue
    logger.info("processed_events_loaded", count=len(processed_events))


def log_processing_state(log: EventProcessingLog):
    """Append processing state to log."""
    with open(processing_log_path, "a") as f:
        f.write(log.model_dump_json() + "\n")
        f.flush()


def save_claims(session_id: str, claims: list[Claim]):
    """Save claims to session-specific JSONL file."""
    file_path = CLAIMS_DIR / f"{session_id}.jsonl"
    with open(file_path, "a") as f:
        for claim in claims:
            f.write(claim.model_dump_json() + "\n")
        f.flush()
    logger.info("claims_saved", session_id=session_id, count=len(claims))


def load_claims(session_id: str) -> list[Claim]:
    """Load all claims for a session."""
    file_path = CLAIMS_DIR / f"{session_id}.jsonl"
    if not file_path.exists():
        return []

    claims = []
    with open(file_path, "r") as f:
        for line in f:
            try:
                claims.append(Claim(**json.loads(line)))
            except (json.JSONDecodeError, ValueError):
                continue

    logger.info("claims_loaded", session_id=session_id, count=len(claims))
    return claims


def save_conflicts(session_id: str, conflicts: list[Conflict]):
    """Save conflicts to session-specific JSONL file."""
    file_path = CONFLICTS_DIR / f"{session_id}.jsonl"
    with open(file_path, "a") as f:
        for conflict in conflicts:
            f.write(conflict.model_dump_json() + "\n")
        f.flush()
    logger.info("conflicts_saved", session_id=session_id, count=len(conflicts))


def load_conflicts(session_id: str) -> list[Conflict]:
    """Load all conflicts for a session."""
    file_path = CONFLICTS_DIR / f"{session_id}.jsonl"
    if not file_path.exists():
        return []

    conflicts = []
    with open(file_path, "r") as f:
        for line in f:
            try:
                conflicts.append(Conflict(**json.loads(line)))
            except (json.JSONDecodeError, ValueError):
                continue

    logger.info("conflicts_loaded", session_id=session_id, count=len(conflicts))
    return conflicts


async def process_event(event: dict, client: httpx.AsyncClient):
    """Process a single event: extract claims and detect conflicts."""
    event_id = event["event_id"]
    session_id = event["session_id"]

    # Skip if already processed
    if event_id in processed_events:
        logger.debug("event_already_processed", event_id=event_id)
        return

    # Log processing start
    log_processing_state(EventProcessingLog(
        event_id=event_id,
        session_id=session_id,
        state=ProcessingState.PROCESSING,
        attempts=1,
        timestamp=datetime.now()
    ))

    try:
        # Extract claims
        logger.info("extracting_claims", event_id=event_id)
        extract_response = await client.post(
            f"{EXTRACTOR_URL}/extract",
            json={
                "event_id": event_id,
                "session_id": session_id,
                "text": event["text"]
            },
            timeout=30.0
        )
        extract_response.raise_for_status()
        extraction_result = extract_response.json()

        claims = [Claim(**c) for c in extraction_result["claims"]]

        # Save claims
        if claims:
            save_claims(session_id, claims)

        # Load all claims for session
        all_claims = load_claims(session_id)

        # Detect conflicts
        logger.info("detecting_conflicts", session_id=session_id)
        conflicts = detect_conflicts(all_claims)

        # Save new conflicts (simple approach: overwrite for now)
        if conflicts:
            # Clear old conflicts file
            conflict_file = CONFLICTS_DIR / f"{session_id}.jsonl"
            if conflict_file.exists():
                conflict_file.unlink()
            save_conflicts(session_id, conflicts)

        # Mark as completed
        log_processing_state(EventProcessingLog(
            event_id=event_id,
            session_id=session_id,
            state=ProcessingState.COMPLETED,
            attempts=1,
            claims_extracted=len(claims),
            timestamp=datetime.now()
        ))

        processed_events.add(event_id)

        logger.info(
            "event_processed",
            event_id=event_id,
            claims_extracted=len(claims),
            total_conflicts=len(conflicts)
        )

    except Exception as e:
        logger.error("event_processing_failed", event_id=event_id, error=str(e))
        log_processing_state(EventProcessingLog(
            event_id=event_id,
            session_id=session_id,
            state=ProcessingState.FAILED,
            attempts=1,
            last_error=str(e),
            timestamp=datetime.now()
        ))


async def poll_ledger():
    """Poll ledger for new events and process them."""
    logger.info("starting_ledger_poll", interval=POLL_INTERVAL)

    async with httpx.AsyncClient() as client:
        while True:
            try:
                # Get all sessions
                sessions_response = await client.get(f"{LEDGER_URL}/ledger/sessions")
                sessions_response.raise_for_status()
                sessions = sessions_response.json()["sessions"]

                # Process each session
                for session_id in sessions:
                    events_response = await client.get(f"{LEDGER_URL}/ledger/session/{session_id}")
                    events_response.raise_for_status()
                    events = events_response.json()

                    for event in events:
                        await process_event(event, client)

            except Exception as e:
                logger.error("poll_failed", error=str(e))

            # Wait before next poll
            await asyncio.sleep(POLL_INTERVAL)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    load_processed_events()
    # Start polling in background
    asyncio.create_task(poll_ledger())
    logger.info("monitor_service_started")


@app.get("/monitor/status")
def get_status():
    """Get pipeline status."""
    return {
        "status": "running",
        "processed_events": len(processed_events),
        "ledger_url": LEDGER_URL,
        "extractor_url": EXTRACTOR_URL,
        "poll_interval": POLL_INTERVAL
    }


@app.get("/monitor/conflicts/{session_id}", response_model=list[Conflict])
def get_conflicts(session_id: str):
    """Get all conflicts for a session."""
    try:
        conflicts = load_conflicts(session_id)
        return conflicts
    except Exception as e:
        logger.error("get_conflicts_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitor/claims/{session_id}", response_model=list[Claim])
def get_claims(session_id: str):
    """Get all claims for a session."""
    try:
        claims = load_claims(session_id)
        return claims
    except Exception as e:
        logger.error("get_claims_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Health check endpoint."""
    try:
        return {
            "status": "healthy",
            "service": "monitor",
            "processed_events": len(processed_events)
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
