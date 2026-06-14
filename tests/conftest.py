"""Shared test fixtures and fakes (T1.1).

No real webcam, Redis, or LM Studio is used anywhere in the suite (NFR-5).
"""
import pytest

from src.brain.vision import Verdict


@pytest.fixture
def jpeg_bytes() -> bytes:
    """A stand-in frame. The pipeline stores/encodes it but never decodes it."""
    return b"\xff\xd8\xff\xe0fake-jpeg-data\xff\xd9"


class FakeResponse:
    """Mimics the bits of a requests.Response that VisionClient uses."""

    def __init__(self, content: str, status: int = 200):
        self._content = content
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise RuntimeError(f"HTTP {self._status}")

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.fixture
def fake_post():
    """Build a `post`-compatible callable that returns the given model content."""

    def make(content, status: int = 200):
        def _post(url, json=None, timeout=None, headers=None):
            return FakeResponse(content, status)

        return _post

    return make


class RecordingPost:
    """A `post` callable that records its last call and returns a fixed response."""

    def __init__(self, content: str):
        self._content = content
        self.url = None
        self.json = None
        self.headers = None

    def __call__(self, url, json=None, timeout=None, headers=None):
        self.url, self.json, self.headers = url, json, headers or {}
        return FakeResponse(self._content)


class FakeClock:
    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float):
        self.t += dt


@pytest.fixture
def clock():
    return FakeClock()


class ScriptedVision:
    """A fake VisionClient that returns a pre-scripted Verdict per classify() call."""

    def __init__(self, verdicts):
        self._verdicts = list(verdicts)
        self.calls = 0

    def classify(self, jpeg) -> Verdict:
        verdict = self._verdicts[self.calls]
        self.calls += 1
        return verdict
