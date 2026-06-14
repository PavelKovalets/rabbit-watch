"""T1.7 — per-visit de-duplication via cooldown (FR-4)."""
from src.brain.detector import Cooldown


def test_first_event_allowed():
    assert Cooldown(seconds=300).allow(now=1000.0) is True


def test_suppressed_within_window():
    cd = Cooldown(seconds=300)
    assert cd.allow(now=1000.0) is True
    assert cd.allow(now=1200.0) is False  # 200s < 300s


def test_allowed_once_window_elapses():
    cd = Cooldown(seconds=300)
    assert cd.allow(now=1000.0) is True
    assert cd.allow(now=1301.0) is True  # 301s >= 300s


def test_uses_injected_clock(clock):
    clock.t = 500.0
    cd = Cooldown(seconds=60, clock=clock)
    assert cd.allow() is True
    clock.advance(30)
    assert cd.allow() is False
    clock.advance(31)
    assert cd.allow() is True
