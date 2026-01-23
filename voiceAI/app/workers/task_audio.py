from celery import shared_task
import base64
import asyncio
from app.audio.services import AudioService
from app.llm.services import LLMService
from app.common.rabbit_mq import publish_audio_response

@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def handle_audio_task(payload: dict):
    """
    Celery task to process audio messages.
    payload: dict containing 'user_id' and 'audio_bytes'
    """
    audio_bytes = base64.b64decode(payload["audio_bytes"])

    print("inside the handle audio task")

    text = asyncio.run(asyncio.to_thread(AudioService.process_audio, audio_bytes))

    if not text.strip():
        return

    response = asyncio.run(LLMService.query_from_text_async(text=text))

    print("LLM response: ", response)

    asyncio.run(
        publish_audio_response(
            user_id=payload.get("user_id"),
            response=response
        )
    )


