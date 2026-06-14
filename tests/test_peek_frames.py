"""Tests for the read-only frame-preview helper."""
from src.tools.peek_frames import extract_jpeg


def test_extract_bytes_key():
    assert extract_jpeg({b"jpeg": b"abc"}) == b"abc"


def test_extract_str_key():
    assert extract_jpeg({"jpeg": b"xyz"}) == b"xyz"


def test_extract_jpg_alias():
    assert extract_jpeg({b"jpg": b"q"}) == b"q"


def test_extract_missing_or_bad_input():
    assert extract_jpeg({b"other": b"1"}) is None
    assert extract_jpeg(None) is None
