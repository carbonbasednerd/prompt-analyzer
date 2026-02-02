"""Storage layer for ledger service."""
from pathlib import Path
import json
from datetime import datetime
from typing import Optional
import structlog

from .models import Event

logger = structlog.get_logger()


class LedgerStorage:
    """Manages JSONL storage with optional SQLite index."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("ledger_storage_initialized", data_dir=str(self.data_dir))

    def append_event(self, event: Event) -> None:
        """Append event to session-specific JSONL file."""
        file_path = self.data_dir / f"{event.session_id}.jsonl"

        # Atomic append
        with open(file_path, "a") as f:
            f.write(event.model_dump_json() + "\n")
            f.flush()

        logger.info(
            "event_appended",
            event_id=event.event_id,
            session_id=event.session_id,
            file=str(file_path)
        )

    def get_session_events(self, session_id: str) -> list[Event]:
        """Read all events for a session."""
        file_path = self.data_dir / f"{session_id}.jsonl"
        if not file_path.exists():
            logger.debug("session_not_found", session_id=session_id)
            return []

        events = []
        with open(file_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    events.append(Event(**json.loads(line)))
                except json.JSONDecodeError as e:
                    logger.warning(
                        "invalid_jsonl_line",
                        session_id=session_id,
                        line_num=line_num,
                        error=str(e)
                    )
                    continue

        logger.info("session_events_loaded", session_id=session_id, count=len(events))
        return events

    def get_events_range(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> list[Event]:
        """Get all events within a time range."""
        all_events = []

        # Read all session files
        for file_path in self.data_dir.glob("*.jsonl"):
            with open(file_path, "r") as f:
                for line in f:
                    try:
                        event = Event(**json.loads(line))

                        # Filter by timestamp
                        if start and event.ts < start:
                            continue
                        if end and event.ts > end:
                            continue

                        all_events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue

        # Sort by timestamp
        all_events.sort(key=lambda e: e.ts)
        logger.info("events_range_loaded", count=len(all_events))
        return all_events

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        sessions = [f.stem for f in self.data_dir.glob("*.jsonl")]
        logger.info("sessions_listed", count=len(sessions))
        return sessions
