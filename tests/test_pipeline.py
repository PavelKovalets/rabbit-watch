"""T2.8 — full per-frame chain with visit tracking + audit log (FR-1..FR-5, FR-9, NFR-2).

Drives RabbitCouchDetector with a scripted vision client, real VisitTracker / EventLog /
ResponseLog — no Redis, camera, or model.
"""
from conftest import ScriptedVision

from src.brain.detector import RabbitCouchDetector, VisitTracker
from src.brain.events import EventLog, ResponseLog
from src.brain.vision import Verdict


def build(tmp_path, verdicts):
    return RabbitCouchDetector(
        vision=ScriptedVision(verdicts),
        tracker=VisitTracker(threshold=0.8, consecutive=3, absence_frames=2),
        event_log=EventLog(output_dir=tmp_path),
        response_log=ResponseLog(output_dir=tmp_path),
    )


def test_visit_logged_when_it_closes(tmp_path, jpeg_bytes):
    # 4 present (open after 3, stay) then 2 absent (close).
    verdicts = [Verdict(True, 0.9, "s", "r")] * 4 + [Verdict.negative()] * 2
    det = build(tmp_path, verdicts)

    results = [det.process(jpeg_bytes, now=float(i)) for i in range(6)]
    events = [r for r in results if r is not None]

    assert len(events) == 1
    rec = det.event_log.read_all()[0]
    assert rec["duration_s"] == 3.0  # present at t=0..3
    assert len(det.response_log.read_all()) == 6  # every call audited (FR-9)


def test_inference_failure_does_not_open_a_false_visit(tmp_path, jpeg_bytes):
    verdicts = [
        Verdict(True, 0.9), Verdict(True, 0.9), Verdict.negative(),
        Verdict(True, 0.9), Verdict(True, 0.9),
    ]
    det = build(tmp_path, verdicts)

    results = [det.process(jpeg_bytes, now=float(i)) for i in range(5)]
    assert all(r is None for r in results)  # never 3 consecutive
    assert det.event_log.read_all() == []
    assert len(det.response_log.read_all()) == 5


def test_low_confidence_stream_logs_no_visit(tmp_path, jpeg_bytes):
    det = build(tmp_path, [Verdict(True, 0.5)] * 10)
    assert all(det.process(jpeg_bytes, now=float(i)) is None for i in range(10))
    assert det.event_log.read_all() == []
