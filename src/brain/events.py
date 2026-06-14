"""Append-only event log + snapshot persistence (FR-5).

Confirmed events are written as JSON Lines at ``RABBITWATCH_EVENTS_LOG``
(default ``<RABBITWATCH_OUTPUT_DIR>/events.jsonl``); each event also writes its
snapshot JPEG under the output dir. The log is the sole input for Phase 2 analytics,
so it must be reproducible from disk alone (FR-6).
"""
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.brain.vision import Verdict
from src.common.logger import get_logger

logger = get_logger("brain.events")

DEFAULT_OUTPUT_DIR = Path(os.getenv("RABBITWATCH_OUTPUT_DIR", "data/brain/detections"))


@dataclass
class EventRecord:
    timestamp: str  # ISO-8601 UTC
    confidence: float
    on_couch: bool
    snapshot: str  # snapshot filename, relative to the output dir


class EventLog:
    def __init__(self, output_dir=None, events_path=None):
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        if events_path:
            self.events_path = Path(events_path)
        elif os.getenv("RABBITWATCH_EVENTS_LOG"):
            self.events_path = Path(os.environ["RABBITWATCH_EVENTS_LOG"])
        else:
            self.events_path = self.output_dir / "events.jsonl"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, verdict: Verdict, snapshot: bytes, ts: float) -> EventRecord:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        snap_name = f"couch_{dt.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        (self.output_dir / snap_name).write_bytes(snapshot)
        record = EventRecord(
            timestamp=dt.isoformat(),
            confidence=verdict.confidence,
            on_couch=verdict.on_couch,
            snapshot=snap_name,
        )
        with open(self.events_path, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")
        return record

    def read_all(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        with open(self.events_path) as f:
            return [json.loads(line) for line in f if line.strip()]
