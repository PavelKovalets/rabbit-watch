"""T2.5 / T2.4 — per-visit event log (FR-5) and raw-response audit log (FR-9)."""
import json

from src.brain.detector import Visit
from src.brain.events import EventLog, ResponseLog
from src.brain.vision import Verdict

START = 1_700_000_000.0


def make_visit(jpeg, start=START, dur=120.0, conf=0.93):
    return Visit(
        start=start, end=start + dur, duration_s=dur, confidence=conf,
        scene="rabbit on the couch", response='{"on_couch": true, "confidence": 0.93}',
        snapshot=jpeg,
    )


def test_record_writes_enriched_record_and_snapshot(tmp_path, jpeg_bytes):
    log = EventLog(output_dir=tmp_path)
    rec = log.record(make_visit(jpeg_bytes))

    snap = tmp_path / rec.snapshot
    assert snap.exists() and snap.read_bytes() == jpeg_bytes

    data = json.loads((tmp_path / "events.jsonl").read_text().splitlines()[0])
    assert data["duration_s"] == 120.0
    assert data["confidence"] == 0.93
    assert data["on_couch"] is True
    assert data["scene"] == "rabbit on the couch"
    assert data["response"] == '{"on_couch": true, "confidence": 0.93}'
    assert data["snapshot"] == rec.snapshot
    assert data["start"].startswith("20") and data["end"].startswith("20")


def test_read_all_round_trips(tmp_path, jpeg_bytes):
    log = EventLog(output_dir=tmp_path)
    log.record(make_visit(jpeg_bytes, start=START, dur=60))
    log.record(make_visit(jpeg_bytes, start=START + 400, dur=30))
    assert [e["duration_s"] for e in log.read_all()] == [60, 30]


def test_read_all_empty_when_no_events(tmp_path):
    assert EventLog(output_dir=tmp_path).read_all() == []


def test_response_log_records_every_call(tmp_path):
    rl = ResponseLog(output_dir=tmp_path)
    rl.record(Verdict(True, 0.9, "a rabbit", '{"on_couch":true,"confidence":0.9}'), ts=START)
    rl.record(Verdict.negative(raw="unparseable"), ts=START + 1)

    rows = rl.read_all()
    assert len(rows) == 2
    assert rows[0]["on_couch"] is True and rows[0]["scene"] == "a rabbit"
    assert rows[0]["response"] == '{"on_couch":true,"confidence":0.9}'
    assert rows[1]["on_couch"] is False and rows[1]["response"] == "unparseable"
