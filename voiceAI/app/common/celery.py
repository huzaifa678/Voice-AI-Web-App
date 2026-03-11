import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")

BROKER_URL = os.environ.get(
    "RABBITMQ_URL", "amqp://guest:guest@localhost:5672//"
)
RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("voiceAI", broker=BROKER_URL, backend=RESULT_BACKEND)

celery_app.config_from_object("django.conf:settings", namespace="CELERY")

celery_app.autodiscover_tasks(
    ["app.workers.task_email"]
)
