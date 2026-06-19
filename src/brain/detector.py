"""Detection logic: visit tracking + the orchestrator that turns verdicts into events.

A *visit* opens when presence is confirmed (confidence ≥ threshold for N consecutive
verdicts, FR-3) and closes once the rabbit has been absent for a sustained number of
verdicts (FR-4); the closed visit carries its start, end, and duration (dwell time, FR-5).
``VisitTracker`` supersedes the Phase 1 ``Confirmer`` + ``Cooldown`` (whose roles —
arrival smoothing and per-visit de-dup — it subsumes).

``VisitTracker`` is pure (no I/O); the caller supplies the timestamp, so it tests without
sleeping or a real endpoint (NFR-5).
"""
import os
from dataclasses import dataclass

from src.brain.vision import Verdict
from src.common.logger import get_logger

logger = get_logger("brain.detector")

DEFAULT_THRESHOLD = float(os.getenv("RABBITWATCH_CONF_THRESHOLD", "0.0"))
DEFAULT_CONSECUTIVE = int(os.getenv("RABBITWATCH_CONSECUTIVE_FRAMES", "1"))
DEFAULT_ABSENCE_FRAMES = int(os.getenv("RABBITWATCH_ABSENCE_FRAMES", "3"))


@dataclass
class Visit:
    """A completed couch visit, ready to persist."""

    start: float  # epoch seconds
    end: float
    duration_s: float
    confidence: float  # peak confidence during the visit
    scene: str
    response: str
    snapshot: bytes


@dataclass
class _Open:
    """Mutable accumulator for the visit currently in progress."""

    start: float
    last: float  # last timestamp the rabbit was present
    peak: float
    scene: str
    response: str
    snapshot: bytes


class VisitTracker:
    """Per-frame state machine: open on sustained presence, close on sustained absence."""

    def __init__(self, threshold=None, consecutive=None, absence_frames=None):
        self.threshold = DEFAULT_THRESHOLD if threshold is None else threshold
        self.consecutive = DEFAULT_CONSECUTIVE if consecutive is None else consecutive
        self.absence_frames = DEFAULT_ABSENCE_FRAMES if absence_frames is None else absence_frames
        self._present_run = 0
        self._absent_run = 0
        self._run_start = 0.0  # timestamp of the first present frame in the current run
        self._open: _Open | None = None

    def _present(self, verdict: Verdict) -> bool:
        return verdict.on_couch and verdict.confidence >= self.threshold

    def observe(self, verdict: Verdict, jpeg: bytes, now: float) -> Visit | None:
        """Feed one verdict; return a completed Visit when one just closed, else None."""
        if self._open is None:
            # Looking for an arrival: need `consecutive` present frames in a row.
            if self._present(verdict):
                if self._present_run == 0:
                    self._run_start = now  # backdate the visit to when presence began
                self._present_run += 1
                if self._present_run >= self.consecutive:
                    self._open = _Open(
                        start=self._run_start, last=now, peak=verdict.confidence,
                        scene=verdict.scene, response=verdict.raw, snapshot=jpeg,
                    )
                    self._present_run = 0
                    self._absent_run = 0
            else:
                self._present_run = 0
            return None

        # In a visit: extend it while present, keep the most confident frame's details.
        if self._present(verdict):
            self._absent_run = 0
            self._open.last = now
            if verdict.confidence >= self._open.peak:
                self._open.peak = verdict.confidence
                self._open.scene = verdict.scene
                self._open.response = verdict.raw
                self._open.snapshot = jpeg
            return None

        # Absent: close the visit once absence is sustained.
        self._absent_run += 1
        if self._absent_run >= self.absence_frames:
            o = self._open
            self._open = None
            self._absent_run = 0
            return Visit(
                start=o.start, end=o.last, duration_s=round(o.last - o.start, 3),
                confidence=o.peak, scene=o.scene, response=o.response, snapshot=o.snapshot,
            )
        return None


class RabbitCouchDetector:
    """Per-frame pipeline: classify → audit-log → visit-track → persist a closed visit."""

    def __init__(self, vision, tracker, event_log, response_log=None, clock=None):
        import time

        self.vision = vision
        self.tracker = tracker
        self.event_log = event_log
        self.response_log = response_log
        self._clock = clock or time.time

    def process(self, jpeg: bytes, now=None):
        """Process one frame; return the EventRecord if a visit just closed."""
        now = self._clock() if now is None else now
        verdict = self.vision.classify(jpeg)
        if self.response_log is not None:
            self.response_log.record(verdict, now)  # every call, confirmed or not (FR-9)
        visit = self.tracker.observe(verdict, jpeg, now)
        if visit is not None:
            record = self.event_log.record(visit)
            logger.info(
                "Logged couch visit: %.0fs (peak confidence=%.2f)",
                visit.duration_s, visit.confidence,
            )
            return record
        return None
