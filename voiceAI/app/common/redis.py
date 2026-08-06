import redis

from app.common.config import config

redis_client = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)
