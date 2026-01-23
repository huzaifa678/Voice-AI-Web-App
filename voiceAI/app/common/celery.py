from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")

celery_app = Celery("voiceAI")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")

celery_app.autodiscover_tasks([
    "app.workers.task_email",
    "app.workers.task_audio"
])

