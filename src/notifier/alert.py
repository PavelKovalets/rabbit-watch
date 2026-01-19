import requests
import os
from src.common.logger import get_logger

logger = get_logger("notifier.alert")

NTFY_TOPIC = os.getenv("RABBITWATCH_NTFY_TOPIC", "rabbit-watch")

def send_ntfy(title: str, message: str, image_path: str | None = None):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    headers = {"Title": title}
    files = None
    data = message
    try:
        if image_path:
            with open(image_path, 'rb') as f:
                files = {'file': f}
                resp = requests.post(url, data=data, headers=headers, files=files)
        else:
            resp = requests.post(url, data=data, headers=headers)
        resp.raise_for_status()
        logger.info("Notification sent")
    except Exception as e:
        logger.exception("Failed to send notification: %s", e)
