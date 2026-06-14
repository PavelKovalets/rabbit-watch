"""T1.5 — temporal smoothing / confirmation (FR-3)."""
from src.brain.detector import Confirmer
from src.brain.vision import Verdict


def v(conf, on_couch=True):
    return Verdict(on_couch=on_couch, confidence=conf)


def test_confirms_after_n_consecutive():
    c = Confirmer(threshold=0.8, consecutive=3)
    assert c.observe(v(0.9)) is False
    assert c.observe(v(0.9)) is False
    assert c.observe(v(0.9)) is True


def test_single_high_frame_among_lows_does_not_confirm():
    c = Confirmer(threshold=0.8, consecutive=3)
    c.observe(v(0.9))
    c.observe(v(0.5))  # resets the run
    assert c.observe(v(0.9)) is False


def test_below_threshold_never_confirms():
    c = Confirmer(threshold=0.8, consecutive=3)
    assert all(c.observe(v(0.79)) is False for _ in range(10))


def test_high_confidence_but_not_on_couch_does_not_count():
    c = Confirmer(threshold=0.8, consecutive=2)
    assert c.observe(v(0.99, on_couch=False)) is False
    assert c.observe(v(0.99, on_couch=False)) is False


def test_stays_confirmed_while_presence_continues():
    c = Confirmer(threshold=0.8, consecutive=3)
    results = [c.observe(v(0.9)) for _ in range(5)]
    assert results == [False, False, True, True, True]
