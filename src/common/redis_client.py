import os
import redis.asyncio as redis

REDIS_URL = os.getenv("RABBITWATCH_REDIS", "redis://localhost:6379")

def get_redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL)
