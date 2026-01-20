import asyncio
import cv2
import os
from pathlib import Path
from datetime import datetime
from src.common.redis_client import get_redis_client
from src.common.logger import get_logger

logger = get_logger("producer.capture")

STREAM_KEY = os.getenv("RABBITWATCH_STREAM", "rabbit-watch-frames")
MAXLEN = int(os.getenv("RABBITWATCH_MAXLEN", "1000"))

# Control whether captured frames are also written to disk for debugging.
SAVE_FRAMES = os.getenv("RABBITWATCH_SAVE_FRAMES_TO_DISK", "False").lower() in ("1", "true", "yes")

async def capture_loop(device_index: int = 0, fps: int = 10):
    r = get_redis_client()
    data_dir = None
    if SAVE_FRAMES:
        data_dir = Path(__file__).resolve().parents[2] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(device_index)
    if not cap.isOpened():
        logger.error("Failed to open webcam")
        return

    delay = 1.0 / fps
    logger.info("Starting capture loop (fps=%s)", fps)
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame read failed, retrying")
                await asyncio.sleep(0.5)
                continue

            _, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            data = jpg.tobytes()
            await r.xadd(STREAM_KEY, {"jpeg": data}, maxlen=MAXLEN, approximate=True)
            if SAVE_FRAMES and data_dir is not None:
                fname = data_dir / f"frame_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                fname.write_bytes(data)
            await asyncio.sleep(delay)
    finally:
        cap.release()

if __name__ == '__main__':
    asyncio.run(capture_loop())
