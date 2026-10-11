"""Redis client factory. One shared client per process."""

from functools import lru_cache

import redis

from config.settings import settings


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
