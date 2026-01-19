import asyncio
import os
from pathlib import Path
from src.common.redis_client import get_redis_client
from src.common.logger import get_logger

logger = get_logger("brain.inference")
STREAM_KEY = os.getenv("RABBITWATCH_STREAM", "frames")
OUTPUT_DIR = Path(os.getenv("RABBITWATCH_OUTPUT_DIR", "data/detections"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

async def consumer_loop():
    r = get_redis_client()
    last_id = '0-0'
    logger.info("Starting inference consumer")
    while True:
        # Block for up to 5s waiting for new frames
        entries = await r.xread({STREAM_KEY: last_id}, count=1, block=5000)
        if not entries:
            continue
        # entries is a list of (stream, [(id, {k:v})])
        for stream, items in entries:
            for entry_id, fields in items:
                last_id = entry_id
                jpeg = fields.get(b'jpeg') or fields.get('jpeg')
                if not jpeg:
                    continue
                # For scaffold: save frame to disk and log
                out_path = OUTPUT_DIR / f"frame_{entry_id.decode() if isinstance(entry_id, bytes) else entry_id}.jpg"
                with open(out_path, 'wb') as f:
                    f.write(jpeg)
                logger.info("Saved frame %s", out_path)
                # TODO: send to local vLLM / vision model for detection

if __name__ == '__main__':
    asyncio.run(consumer_loop())
