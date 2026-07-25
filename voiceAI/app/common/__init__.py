from .celery import celery_app
from .logger import setup_logging

setup_logging()

__all__ = ("celery_app",)
