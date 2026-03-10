import os
from dotenv import load_dotenv
import redis

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL") or os.getenv("CELERY_RESULT_BACKEND")

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
