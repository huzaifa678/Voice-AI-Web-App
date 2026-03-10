import base64
import asyncio

from app.common.celery import celery_app
from app.common.rabbit_mq import publish_audio_response
from app.tts.services import TTSService


@celery_app.task(name="app.workers.task_tts.process_tts_task", queue="tts_tasks")
def process_tts_task(text: str, user_id: str | None):
    """Convert text to speech and publish it back to the audio response exchange."""

    if not text:
        return

    audio_bytes = TTSService.synthesize(text)
    if not audio_bytes:
        return

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    asyncio.run(publish_audio_response(user_id=user_id, audio_bytes=audio_b64))
