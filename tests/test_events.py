"""T1.9 — event log + snapshot persistence (FR-5)."""
import json

from src.brain.events import EventLog
from src.brain.vision import Verdict

TS = 1_700_000_000.0  # fixed wall-clock for deterministic filenames


def test_record_writes_line_and_snapshot(tmp_path, jpeg_bytes):
    log = EventLog(output_dir=tmp_path)
    rec = log.record(Verdict(True, 0.91), jpeg_bytes, ts=TS)

    snapshot = tmp_path / rec.snapshot
    assert snapshot.exists()
    assert snapshot.read_bytes() == jpeg_bytes

    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["confidence"] == 0.91
    assert data["on_couch"] is True
    assert data["snapshot"] == rec.snapshot
    assert data["timestamp"].startswith("2023-")  # ISO-8601 UTC


def test_read_all_round_trips(tmp_path, jpeg_bytes):
    log = EventLog(output_dir=tmp_path)
    log.record(Verdict(True, 0.9), jpeg_bytes, ts=TS)
    log.record(Verdict(True, 0.8), jpeg_bytes, ts=TS + 400)

    events = log.read_all()
    assert [e["confidence"] for e in events] == [0.9, 0.8]


def test_read_all_empty_when_no_events(tmp_path):
    assert EventLog(output_dir=tmp_path).read_all() == []


def test_events_path_override(tmp_path, jpeg_bytes):
    custom = tmp_path / "nested" / "log.jsonl"
    log = EventLog(output_dir=tmp_path, events_path=custom)
    log.record(Verdict(True, 0.9), jpeg_bytes, ts=TS)
    assert custom.exists()
