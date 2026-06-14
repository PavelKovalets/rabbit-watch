"""Vision client: ask the model whether the rabbit is on the couch (FR-2).

Calls an OpenAI-compatible chat completions endpoint (LM Studio on the Hyper-V host;
see spec/infrastructure.md) with a frame image and the `rabbit_on_couch` prompt, and
parses a structured ``{on_couch, confidence}`` verdict.

Network and parse failures are converted to a "not on couch" verdict (NFR-2) so the
consumer never crashes on a flaky endpoint.
"""
import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests

from src.common.logger import get_logger

logger = get_logger("brain.vision")

PROMPTS_PATH = Path(__file__).with_name("prompts.yaml")
DEFAULT_URL = os.getenv("RABBITWATCH_VLM_URL", "http://localhost:1234/v1")
DEFAULT_MODEL = os.getenv("RABBITWATCH_VLM_MODEL", "gemma-4")
DEFAULT_TIMEOUT = float(os.getenv("RABBITWATCH_VLM_TIMEOUT", "30"))
DEFAULT_API_KEY = os.getenv("RABBITWATCH_VLM_API_KEY")  # None disables the auth header


@dataclass(frozen=True)
class Verdict:
    """One frame's judgement: is the rabbit on the couch, and how sure."""

    on_couch: bool
    confidence: float

    @classmethod
    def negative(cls) -> "Verdict":
        """The safe default used whenever a frame can't be judged (NFR-2)."""
        return cls(on_couch=False, confidence=0.0)


def load_prompt(name: str = "rabbit_on_couch", path: Path = PROMPTS_PATH) -> list[dict]:
    import yaml  # lazy: keeps the module importable without PyYAML for unit tests

    with open(path) as f:
        return yaml.safe_load(f)[name]


def parse_verdict(content: str) -> Verdict:
    """Extract ``{on_couch, confidence}`` from model text, leniently.

    Raises ValueError if no JSON object is present; the caller turns that into a
    negative verdict.
    """
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in response: {content!r}")
    data = json.loads(match.group(0))
    on_couch = data.get("on_couch")
    if on_couch is None:  # tolerate a couple of alternate spellings
        on_couch = data.get("present", data.get("presence", False))
    return Verdict(on_couch=bool(on_couch), confidence=float(data.get("confidence", 0.0)))


class VisionClient:
    def __init__(self, url=None, model=None, prompt=None, timeout=None, api_key=None, post=None):
        self.url = (url or DEFAULT_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.prompt = prompt if prompt is not None else load_prompt()
        self.timeout = DEFAULT_TIMEOUT if timeout is None else timeout
        self.api_key = api_key if api_key is not None else DEFAULT_API_KEY
        self._post = post or requests.post  # injectable for tests

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _build_messages(self, jpeg: bytes) -> list[dict]:
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        messages = []
        for turn in self.prompt:
            if turn["role"] == "user":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": turn["content"]},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                )
            else:
                messages.append({"role": turn["role"], "content": turn["content"]})
        return messages

    def classify(self, jpeg: bytes) -> Verdict:
        payload = {
            "model": self.model,
            "messages": self._build_messages(jpeg),
            "temperature": 0,
        }
        try:
            resp = self._post(
                f"{self.url}/chat/completions",
                json=payload,
                timeout=self.timeout,
                headers=self._headers(),
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("Vision request failed; treating frame as not-on-couch")
            return Verdict.negative()
        try:
            return parse_verdict(content)
        except Exception:
            logger.warning("Unparseable verdict, treating as not-on-couch: %r", content)
            return Verdict.negative()
