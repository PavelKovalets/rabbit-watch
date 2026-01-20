import asyncio
import os
from pathlib import Path
from src.common.redis_client import get_redis_client
from src.common.logger import get_logger

logger = get_logger("brain.inference")
STREAM_KEY = os.getenv("RABBITWATCH_STREAM", "rabbit-watch-frames")
OUTPUT_DIR = Path(os.getenv("RABBITWATCH_OUTPUT_DIR", "data/brain/detections"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

async def consumer_loop():
    r = get_redis_client()
    last_id = '0-0'
    logger.info("Starting inference consumer (saving frames to %s)", OUTPUT_DIR)
    while True:
        try:
            # Block for up to 5s waiting for new frames
            entries = await r.xread({STREAM_KEY: last_id}, count=10, block=5000)
        except Exception:
            logger.exception("Redis read failed, retrying in 1s")
            await asyncio.sleep(1)
            continue

        if not entries:
            continue

        # entries is a list of (stream, [(id, {k:v})])
        for stream, items in entries:
            for entry_id, fields in items:
                last_id = entry_id
                jpeg = None
                # fields may have bytes or str keys
                if isinstance(fields, dict):
                    jpeg = fields.get(b'jpeg') or fields.get('jpeg') or fields.get(b'jpg') or fields.get('jpg')
                if not jpeg:
                    continue

                id_str = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
                out_path = OUTPUT_DIR / f"frame_{id_str}.jpg"
                try:
                    with open(out_path, 'wb') as f:
                        f.write(jpeg)
                    logger.info("Saved frame %s", out_path)
                except Exception:
                    logger.exception("Failed saving frame %s", out_path)

if __name__ == '__main__':
    asyncio.run(consumer_loop())
