"""T2.6 — visit dwell tracking (FR-3 arrival, FR-4 one-per-visit, FR-5 duration)."""
from src.brain.detector import Visit, VisitTracker
from src.brain.vision import Verdict

JPEG = b"frame"


def v(conf, on_couch=True, scene="s", raw="r"):
    return Verdict(on_couch=on_couch, confidence=conf, scene=scene, raw=raw)


def absent():
    return Verdict.negative()


def test_opens_after_consecutive_and_closes_after_absence():
    t = VisitTracker(threshold=0.8, consecutive=3, absence_frames=2)
    assert t.observe(v(0.9), JPEG, 0) is None  # present 1
    assert t.observe(v(0.9), JPEG, 1) is None  # present 2
    assert t.observe(v(0.9), JPEG, 2) is None  # present 3 -> visit opens (start=0)
    assert t.observe(v(0.9), JPEG, 3) is None  # still present, last=3
    assert t.observe(absent(), JPEG, 4) is None  # absent 1
    visit = t.observe(absent(), JPEG, 5)  # absent 2 -> close
    assert isinstance(visit, Visit)
    assert visit.start == 0 and visit.end == 3
    assert visit.duration_s == 3


def test_single_present_among_absences_never_opens():
    t = VisitTracker(threshold=0.8, consecutive=3, absence_frames=2)
    out = []
    for i, ver in enumerate([v(0.9), absent(), v(0.9), v(0.9), absent()]):
        out.append(t.observe(ver, JPEG, i))
    assert out == [None, None, None, None, None]  # never 3 in a row


def test_below_threshold_never_opens():
    t = VisitTracker(threshold=0.8, consecutive=2, absence_frames=2)
    assert all(t.observe(v(0.5), JPEG, i) is None for i in range(10))


def test_continuous_stay_is_one_visit():
    t = VisitTracker(threshold=0.8, consecutive=2, absence_frames=2)
    results = [t.observe(v(0.9), JPEG, i) for i in range(20)]
    assert all(r is None for r in results)  # never closes while present


def test_brief_absence_does_not_split_visit():
    t = VisitTracker(threshold=0.8, consecutive=2, absence_frames=3)
    t.observe(v(0.9), JPEG, 0)
    t.observe(v(0.9), JPEG, 1)  # open, start=0
    assert t.observe(absent(), JPEG, 2) is None  # absent 1
    assert t.observe(v(0.9), JPEG, 3) is None  # present -> absence resets, last=3
    assert t.observe(absent(), JPEG, 4) is None  # absent 1
    assert t.observe(absent(), JPEG, 5) is None  # absent 2
    visit = t.observe(absent(), JPEG, 6)  # absent 3 -> close
    assert visit.end == 3 and visit.duration_s == 3  # one visit, not split


def test_defaults_capture_single_low_confidence_detection():
    # Defaults (2026-06-18): threshold 0.0 + 1 consecutive frame -> any single on_couch
    # frame, at any confidence, opens a visit.
    from src.brain import detector

    assert detector.DEFAULT_THRESHOLD == 0.0
    assert detector.DEFAULT_CONSECUTIVE == 1
    t = VisitTracker(absence_frames=1)  # threshold and consecutive use the defaults
    assert t.observe(v(0.05), JPEG, 0) is None  # single low-confidence on_couch -> opens
    visit = t.observe(absent(), JPEG, 1)
    assert visit is not None and visit.confidence == 0.05


def test_peak_confidence_scene_and_snapshot_captured():
    t = VisitTracker(threshold=0.8, consecutive=1, absence_frames=1)
    t.observe(Verdict(True, 0.85, "low", "r1"), b"first", 0)  # opens
    t.observe(Verdict(True, 0.95, "high", "r2"), b"best", 1)  # new peak
    visit = t.observe(absent(), JPEG, 2)  # close
    assert visit.confidence == 0.95
    assert visit.scene == "high"
    assert visit.snapshot == b"best"
