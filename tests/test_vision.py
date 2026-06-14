"""T1.2 — vision client parsing and failure handling (FR-2, NFR-2); auth header (NFR-6)."""
from conftest import RecordingPost

from src.brain.vision import Verdict, VisionClient, load_prompt, parse_verdict

PROMPT = [{"role": "user", "content": "on couch?"}]
OK = '{"on_couch": true, "confidence": 0.9}'


def test_parse_well_formed():
    assert parse_verdict('{"on_couch": true, "confidence": 0.95}') == Verdict(True, 0.95)


def test_parse_embedded_in_prose():
    content = 'Result: {"on_couch": false, "confidence": 0.1} — hope that helps'
    assert parse_verdict(content) == Verdict(False, 0.1)


def test_classify_parses_response(jpeg_bytes, fake_post):
    client = VisionClient(prompt=PROMPT, post=fake_post('{"on_couch": true, "confidence": 0.9}'))
    assert client.classify(jpeg_bytes) == Verdict(True, 0.9)


def test_classify_malformed_is_negative(jpeg_bytes, fake_post):
    client = VisionClient(prompt=PROMPT, post=fake_post("I'm not sure what I see"))
    assert client.classify(jpeg_bytes) == Verdict.negative()


def test_classify_http_error_is_negative(jpeg_bytes, fake_post):
    client = VisionClient(prompt=PROMPT, post=fake_post("ignored", status=500))
    assert client.classify(jpeg_bytes) == Verdict.negative()


def test_classify_connection_error_is_negative(jpeg_bytes):
    def boom(url, json=None, timeout=None):
        raise ConnectionError("connection refused")

    client = VisionClient(prompt=PROMPT, post=boom)
    assert client.classify(jpeg_bytes) == Verdict.negative()


def test_sends_bearer_header_when_key_set(jpeg_bytes):
    post = RecordingPost(OK)
    VisionClient(prompt=PROMPT, api_key="secret-token", post=post).classify(jpeg_bytes)
    assert post.headers.get("Authorization") == "Bearer secret-token"


def test_no_auth_header_when_no_key(jpeg_bytes):
    post = RecordingPost(OK)
    VisionClient(prompt=PROMPT, api_key=None, post=post).classify(jpeg_bytes)
    assert "Authorization" not in post.headers


def test_prompt_yaml_has_couch_template():
    # T1.3: the shipped prompt asks about the couch and a structured reply.
    prompt = load_prompt("rabbit_on_couch")
    text = " ".join(turn["content"] for turn in prompt).lower()
    assert "couch" in text
    assert "on_couch" in text and "confidence" in text
