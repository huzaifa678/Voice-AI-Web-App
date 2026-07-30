import time
from .redis import redis_client


class RateLimitExceeded(Exception):
    pass


class TokenBucket:
    """
    Token bucket rate limiter backed by Redis.

    Each key has a bucket that refills at `refill_rate` tokens per `per_seconds`.
    The bucket caps at `bucket_capacity` tokens. A request costs 1 token.
    Uses a single Redis key with HSET and atomic Lua script for refill+check.
    """

    def __init__(self, bucket_capacity: int, refill_rate: float, per_seconds: int):
        self.bucket_capacity = bucket_capacity
        self.refill_rate = refill_rate
        self.per_seconds = per_seconds

    def allow(self, key: str) -> bool:
        """
        Try to consume 1 token. Returns True if allowed, False if rate-limited.
        Uses an atomic Lua script to avoid race conditions.
        """
        redis_key = f"token_bucket:{key}"
        now = time.time()

        lua_script = """
        local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
        local tokens = tonumber(bucket[1]) or ARGV[3]
        local last_ts = tonumber(bucket[2]) or ARGV[4]
        local now = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local refill_rate = tonumber(ARGV[3])
        local per_seconds = tonumber(ARGV[4])
        local cost = tonumber(ARGV[5])

        local elapsed = now - last_ts
        local refill = elapsed * (refill_rate / per_seconds)
        tokens = math.min(capacity, tokens + refill)

        if tokens >= cost then
            tokens = tokens - cost
            redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
            redis.call('EXPIRE', KEYS[1], ARGV[6])
            return 1
        else
            redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', last_ts)
            redis.call('EXPIRE', KEYS[1], ARGV[6])
            return 0
        end
        """

        result = redis_client.eval(
            lua_script,
            1,
            redis_key,
            now,
            self.bucket_capacity,
            self.refill_rate,
            self.per_seconds,
            1,  # cost per request
            self.per_seconds * 2,  # TTL: 2x window to keep key alive
        )

        return result == 1


def rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
):
    """
    Token bucket rate limiter.

    Args:
        key: Unique identifier for the rate limit key (e.g. user ID, IP).
        limit: Maximum number of requests allowed per window (bucket capacity).
        window_seconds: Time window in seconds over which the rate is enforced.

    Raises:
        RateLimitExceeded: If the token bucket is empty (rate limit hit).
    """
    bucket = TokenBucket(
        bucket_capacity=limit,
        refill_rate=limit,
        per_seconds=window_seconds,
    )

    if not bucket.allow(key):
        raise RateLimitExceeded("Too many requests")
