import asyncio
import os

from dotenv import load_dotenv

# Load .env (e.g. RABBITWATCH_VLM_API_KEY) before the brain modules read their config.
load_dotenv()

from src.brain.detector import Confirmer, Cooldown, RabbitCouchDetector
from src.brain.events import EventLog
from src.brain.vision import VisionClient
from src.common.logger import get_logger
from src.common.redis_client import get_redis_client

logger = get_logger("brain.inference")
STREAM_KEY = os.getenv("RABBITWATCH_STREAM", "rabbit-watch-frames")


def build_detector() -> RabbitCouchDetector:
    return RabbitCouchDetector(
        vision=VisionClient(),
        confirmer=Confirmer(),
        cooldown=Cooldown(),
        event_log=EventLog(),
    )


def _extract_jpeg(fields):
    # Redis may return bytes or str keys depending on client decoding.
    if not isinstance(fields, dict):
        return None
    return fields.get(b"jpeg") or fields.get("jpeg") or fields.get(b"jpg") or fields.get("jpg")


async def consumer_loop(detector: RabbitCouchDetector | None = None):
    detector = detector or build_detector()
    r = get_redis_client()
    # "$" = only frames that arrive after we start; don't replay the buffered backlog
    # on (re)start. Freshness over completeness (NFR-4).
    last_id = "$"
    logger.info("Starting inference consumer (rabbit-on-couch detection)")
    while True:
        try:
            # Block up to 5s for new frames; batches of 10.
            entries = await r.xread({STREAM_KEY: last_id}, count=10, block=5000)
        except Exception:
            logger.exception("Redis read failed, retrying in 1s")
            await asyncio.sleep(1)
            continue

        if not entries:
            continue

        for _stream, items in entries:
            for entry_id, fields in items:
                last_id = entry_id
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
