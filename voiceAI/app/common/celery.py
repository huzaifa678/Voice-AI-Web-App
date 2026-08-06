import os
from celery import Celery

from app.common.config import config

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")

celery_app = Celery(
    "voiceAI",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
)

celery_app.config_from_object("django.conf:settings", namespace="CELERY")

celery_app.autodiscover_tasks(["app.workers.task_email"])
