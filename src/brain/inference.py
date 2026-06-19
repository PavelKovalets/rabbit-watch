import asyncio
import os

from dotenv import load_dotenv

# Load .env (e.g. RABBITWATCH_VLM_API_KEY) before the brain modules read their config.
load_dotenv()

from src.brain.detector import RabbitCouchDetector, VisitTracker
from src.brain.events import EventLog, ResponseLog
from src.brain.vision import VisionClient
from src.common.logger import get_logger
from src.common.redis_client import get_redis_client

logger = get_logger("brain.inference")
STREAM_KEY = os.getenv("RABBITWATCH_STREAM", "rabbit-watch-frames")


def build_detector() -> RabbitCouchDetector:
    return RabbitCouchDetector(
        vision=VisionClient(),
        tracker=VisitTracker(),
        event_log=EventLog(),
        response_log=ResponseLog(),
    )


def _extract_jpeg(fields):
    # Redis may return bytes or str keys depending on client decoding.
    if not isinstance(fields, dict):
        return None
    return fields.get(b"jpeg") or fields.get("jpeg") or fields.get(b"jpg") or fields.get("jpg")


# How often to poll for a new frame when none has arrived since the last one analyzed.
POLL_INTERVAL = 0.5


async def consumer_loop(detector: RabbitCouchDetector | None = None):
    detector = detector or build_detector()
    r = get_redis_client()
    last_seen = None
    logger.info("Starting inference consumer (rabbit-on-couch detection; newest-frame)")
    while True:
        try:
            # Always analyze the *newest* frame and drop everything in between: inference
            # is slower than capture, so chasing a backlog would just lag (NFR-4).
            entries = await r.xrevrange(STREAM_KEY, count=1)
        except Exception:
            logger.exception("Redis read failed, retrying in 1s")
            await asyncio.sleep(1)
            continue

        if not entries:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        entry_id, fields = entries[0]
        if entry_id == last_seen:
            await asyncio.sleep(POLL_INTERVAL)  # no new frame since the last one analyzed
            continue
        last_seen = entry_id

        jpeg = _extract_jpeg(fields)
        if not jpeg:
            continue
        try:
            # Vision call is blocking HTTP; keep it off the event loop.
            await asyncio.to_thread(detector.process, jpeg)
        except Exception:
            logger.exception("Detector failed on frame %s", entry_id)


if __name__ == "__main__":
    asyncio.run(consumer_loop())
