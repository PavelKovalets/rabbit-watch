"""Preview frames from the Redis stream by dumping recent JPEGs to disk (read-only).

    python -m src.tools.peek_frames [-n N] [-o DIR] [--oldest]

Reads are non-destructive — `XREVRANGE`/`XRANGE` never modify the stream — so this is a
safe way to eyeball what the camera is sending without touching the buffer. Honours
`RABBITWATCH_REDIS` / `RABBITWATCH_STREAM` (and `.env`), so it works from the guest
against host Redis.
"""
import argparse
import os
from pathlib import Path

import redis
from dotenv import load_dotenv

from src.common.logger import get_logger

load_dotenv()
logger = get_logger("tools.peek_frames")

REDIS_URL = os.getenv("RABBITWATCH_REDIS", "redis://localhost:6379")
STREAM_KEY = os.getenv("RABBITWATCH_STREAM", "rabbit-watch-frames")


def extract_jpeg(fields):
    """Pull the JPEG bytes out of a stream entry (Redis may use bytes or str keys)."""
    if not isinstance(fields, dict):
        return None
    return fields.get(b"jpeg") or fields.get("jpeg") or fields.get(b"jpg") or fields.get("jpg")


def dump_frames(count: int, out_dir, oldest: bool = False):
    """Write up to `count` frames to `out_dir`; return (stream_length, [paths])."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = redis.from_url(REDIS_URL, socket_connect_timeout=5)
    total = r.xlen(STREAM_KEY)
    entries = (
        r.xrange(STREAM_KEY, count=count) if oldest
        else r.xrevrange(STREAM_KEY, count=count)
    )
    written = []
    for entry_id, fields in entries:
        jpeg = extract_jpeg(fields)
        if not jpeg:
            continue
        eid = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
        path = out_dir / f"frame_{eid}.jpg"
        path.write_bytes(jpeg)
        written.append(path)
    return total, written


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-n", "--count", type=int, default=5, help="number of frames (default 5)")
    ap.add_argument("-o", "--out-dir", default="data/preview", help="output dir (default data/preview)")
    ap.add_argument("--oldest", action="store_true", help="oldest frames instead of newest")
    args = ap.parse_args()

    total, written = dump_frames(args.count, args.out_dir, args.oldest)
    print(f"stream={STREAM_KEY} XLEN={total} (read-only, stream untouched)")
    for path in written:
        print(f"  wrote {path} ({path.stat().st_size} bytes)")
    if not written:
        print("  no frames found")


if __name__ == "__main__":
    main()
