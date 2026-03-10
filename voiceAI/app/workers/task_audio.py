import base64
import asyncio

from app.common.celery import celery_app
from app.common.rabbit_mq import publish_audio_response
from app.audio.services import AudioService
from app.llm.services import LLMService


@celery_app.task(name="app.workers.task_audio.process_audio_task", queue="audio_tasks")
def process_audio_task(user_id: str | None, audio_bytes_b64: str):
    """Process an incoming audio task (Celery task)."""

    audio_bytes = base64.b64decode(audio_bytes_b64)

    text = AudioService.process_audio(audio_bytes)
    if not text:
        return

    text = text.strip()
    if not text:
        return

    response = asyncio.run(LLMService.query_from_text_async(text=text))

    asyncio.run(publish_audio_response(user_id=user_id, response=response))

    from app.workers.task_tts import process_tts_task

    process_tts_task.delay(response, user_id)
