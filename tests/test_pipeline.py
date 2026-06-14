"""T1.11 — integration of the full per-frame chain (FR-1..FR-5, NFR-2).

Drives RabbitCouchDetector directly (the same object the async brain loop calls per
frame) with a scripted vision client, real Confirmer/Cooldown/EventLog, and an
explicit clock — no Redis, camera, or model.
"""
from conftest import ScriptedVision

from src.brain.detector import Confirmer, Cooldown, RabbitCouchDetector
from src.brain.events import EventLog
from src.brain.vision import Verdict


def build(tmp_path, verdicts):
    return RabbitCouchDetector(
        vision=ScriptedVision(verdicts),
        confirmer=Confirmer(threshold=0.8, consecutive=3),
        cooldown=Cooldown(seconds=300),
        event_log=EventLog(output_dir=tmp_path),
    )


def test_sustained_presence_logs_exactly_one_event(tmp_path, jpeg_bytes):
    det = build(tmp_path, [Verdict(True, 0.9)] * 5)
    results = [det.process(jpeg_bytes, now=float(i)) for i in range(5)]

    events = [r for r in results if r is not None]
    assert len(events) == 1  # confirmed at frame 3; cooldown suppresses the rest
    assert det.event_log.read_all()[0]["confidence"] == 0.9


def test_inference_failure_midstream_yields_no_event(tmp_path, jpeg_bytes):
    # Two highs, a failure (negative verdict, as the vision client returns on error),
    # then highs — never three consecutive, so nothing is logged (NFR-2 + FR-3).
    verdicts = [
        Verdict(True, 0.9),
        Verdict(True, 0.9),
        Verdict.negative(),
        Verdict(True, 0.9),
        Verdict(True, 0.9),
    ]
    det = build(tmp_path, verdicts)
    results = [det.process(jpeg_bytes, now=float(i)) for i in range(5)]

    assert all(r is None for r in results)
    assert det.event_log.read_all() == []


def test_second_visit_after_cooldown_logs_again(tmp_path, jpeg_bytes):
    det = build(tmp_path, [Verdict(True, 0.9)] * 8)
    # Confirmed at t=2 -> event. t=3,4 within cooldown -> suppressed.
    # t>=302 is past the 300s window -> a second event.
    times = [0, 1, 2, 3, 4, 302, 303, 304]
    events = [det.process(jpeg_bytes, now=float(t)) for t in times]

    assert len([e for e in events if e is not None]) == 2
    assert len(det.event_log.read_all()) == 2


def test_low_confidence_stream_logs_nothing(tmp_path, jpeg_bytes):
    det = build(tmp_path, [Verdict(True, 0.5)] * 10)
    results = [det.process(jpeg_bytes, now=float(i)) for i in range(10)]
    assert all(r is None for r in results)
