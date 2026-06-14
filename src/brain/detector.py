"""Detection logic and the orchestrator that turns verdicts into events.

- ``Confirmer`` — temporal smoothing: confirm only after N consecutive
  above-threshold verdicts (FR-3).
- ``Cooldown`` — one event per visit: suppress repeats within a window (FR-4).
- ``RabbitCouchDetector`` — wires vision → confirm → cooldown → event log.

Confirmer and Cooldown are pure (no I/O) and take an injectable clock, so they test
without sleeping or a real endpoint (NFR-5).
"""
import os
import time

from src.brain.vision import Verdict
from src.common.logger import get_logger

logger = get_logger("brain.detector")

DEFAULT_THRESHOLD = float(os.getenv("RABBITWATCH_CONF_THRESHOLD", "0.8"))
DEFAULT_CONSECUTIVE = int(os.getenv("RABBITWATCH_CONSECUTIVE_FRAMES", "3"))
DEFAULT_COOLDOWN = float(os.getenv("RABBITWATCH_COOLDOWN_SECONDS", "300"))


class Confirmer:
    """Confirms presence once confidence ≥ threshold for N consecutive verdicts."""

    def __init__(self, threshold=None, consecutive=None):
        self.threshold = DEFAULT_THRESHOLD if threshold is None else threshold
        self.consecutive = DEFAULT_CONSECUTIVE if consecutive is None else consecutive
        self._run = 0

    def observe(self, verdict: Verdict) -> bool:
        """Feed one verdict; return whether presence is currently confirmed."""
        if verdict.on_couch and verdict.confidence >= self.threshold:
            self._run += 1
        else:
            self._run = 0
        return self._run >= self.consecutive


class Cooldown:
    """Permits one event per ``seconds`` window (FR-4)."""

    def __init__(self, seconds=None, clock=time.monotonic):
        self.seconds = DEFAULT_COOLDOWN if seconds is None else seconds
        self._clock = clock
        self._last = None

    def allow(self, now=None) -> bool:
        """Return True (and arm the window) if no event happened within the window."""
        now = self._clock() if now is None else now
        if self._last is None or (now - self._last) >= self.seconds:
            self._last = now
            return True
        return False


class RabbitCouchDetector:
    """Per-frame pipeline: classify → confirm → cooldown → log a confirmed event."""

    def __init__(self, vision, confirmer, cooldown, event_log, clock=time.time):
        self.vision = vision
        self.confirmer = confirmer
        self.cooldown = cooldown
        self.event_log = event_log
        self._clock = clock

    def process(self, jpeg: bytes, now=None):
        """Process one frame; return the EventRecord if it confirmed a new event."""
        now = self._clock() if now is None else now
        verdict = self.vision.classify(jpeg)
        if self.confirmer.observe(verdict) and self.cooldown.allow(now):
            record = self.event_log.record(verdict, jpeg, now)
            logger.info(
                "Confirmed rabbit-on-couch event (confidence=%.2f)", verdict.confidence
            )
            return record
        return None
