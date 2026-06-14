"""Persistence: per-visit event log + snapshot (FR-5), and a raw-response audit log (FR-9).

- ``EventLog`` — one JSON-Lines record per confirmed visit at ``RABBITWATCH_EVENTS_LOG``
  (default ``<RABBITWATCH_OUTPUT_DIR>/events.jsonl``), with the visit's snapshot JPEG
  under the output dir. This is the input for Phase 2 analytics (FR-6), so it must be
  reproducible from disk alone.
- ``ResponseLog`` — every model classification, confirmed or not, at
  ``RABBITWATCH_RESPONSES_LOG`` (default ``<RABBITWATCH_OUTPUT_DIR>/responses.jsonl``).
"""
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.common.logger import get_logger

logger = get_logger("brain.events")

DEFAULT_OUTPUT_DIR = Path(os.getenv("RABBITWATCH_OUTPUT_DIR", "data/brain/detections"))


def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@dataclass
class EventRecord:
    start: str  # ISO-8601 UTC
    end: str  # ISO-8601 UTC
    duration_s: float
    confidence: float
    on_couch: bool
    scene: str
    response: str
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

    def record(self, visit) -> EventRecord:
        """Persist a completed visit (duck-typed: start/end/duration_s/confidence/scene/
        response/snapshot) plus its snapshot JPEG."""
        start_dt = datetime.fromtimestamp(visit.start, tz=timezone.utc)
        snap_name = f"couch_{start_dt.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        (self.output_dir / snap_name).write_bytes(visit.snapshot)
        record = EventRecord(
            start=start_dt.isoformat(),
            end=_utc_iso(visit.end),
            duration_s=visit.duration_s,
            confidence=visit.confidence,
            on_couch=True,
            scene=visit.scene,
            response=visit.response,
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


class ResponseLog:
    """Append-only audit log of every model classification (FR-9)."""

    def __init__(self, output_dir=None, path=None):
        output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        if path:
            self.path = Path(path)
        elif os.getenv("RABBITWATCH_RESPONSES_LOG"):
            self.path = Path(os.environ["RABBITWATCH_RESPONSES_LOG"])
        else:
            self.path = output_dir / "responses.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, verdict, ts: float) -> None:
        line = {
            "timestamp": _utc_iso(ts),
            "on_couch": verdict.on_couch,
            "confidence": verdict.confidence,
            "scene": verdict.scene,
            "response": verdict.raw,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(line) + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            return [json.loads(line) for line in f if line.strip()]
