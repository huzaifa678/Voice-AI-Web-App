import time
from .redis import redis_client

class RateLimitExceeded(Exception):
    pass


def rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
):
    """
    Sliding window rate limiter using Redis
    """
    now = int(time.time())
    redis_key = f"rate:{key}"

    pipe = redis_client.pipeline()
    pipe.zadd(redis_key, {now: now})
    pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
    pipe.zcard(redis_key)
    pipe.expire(redis_key, window_seconds)
    _, _, count, _ = pipe.execute()

    if count > limit:
        raise RateLimitExceeded("Too many requests")
