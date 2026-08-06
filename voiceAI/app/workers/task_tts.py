import asyncio
import base64
import json
import time
import aio_pika
from app.common.config import config
from app.common.rabbit_mq import get_connection, publish_audio_response
from app.common.logger import get_logger
from app.audio.metrics import VoiceMetrics
from app.common.telemetry import context_from_metadata, record_exception, setup_telemetry, tracer
from app.tts.providers import get_tts_provider

setup_telemetry("voice-ai-tts-worker")
logger = get_logger(__name__)
tracer = tracer(__name__)

ENVIRONMENT = config.ENVIRONMENT
tts_provider = get_tts_provider()


async def handle_tts_message(message: aio_pika.IncomingMessage):
    payload = json.loads(message.body)
    text = payload["text"]
    user_id = payload["user_id"]
    parent_context = context_from_metadata(payload.get("trace", {}).items())

    with tracer.start_as_current_span(
        "voice.worker.tts_message",
        context=parent_context,
        attributes={"voice.tts.text_chars": len(text)},
    ) as span:
        try:
            logger.info("inside the handle tts message method")

            start_time = time.time()  # start timer
            # Synthesize audio in a thread (blocks TTS CPU/GPU work here)
            audio_bytes = await asyncio.to_thread(tts_provider.synthesize, text)
            end_time = time.time()  # end timer
            VoiceMetrics.observe("tts", start_time, end_time)
            span.set_attribute("voice.tts.audio_bytes", len(audio_bytes))

            logger.info(
                "TTS synthesis took %.2f seconds for text length %d",
                end_time - start_time,
                len(text),
            )

            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            logger.info("Audio bytes synthesized, publishing response")

            await publish_audio_response(user_id=user_id, audio_bytes=audio_b64)

            logger.info("Audio response published")

            await message.ack()

        except Exception as e:
            VoiceMetrics.count_error("tts_worker")
            record_exception(span, e)
            await message.nack(requeue=False)
            raise e


async def main():
    connection = await get_connection()
    channel = await connection.channel()

    queue = await channel.declare_queue("tts_tasks", durable=True)

    if ENVIRONMENT != "local":
        logger.info("[*] Loading TTS model...")
        await asyncio.to_thread(tts_provider.load)
        logger.info("[*] TTS model loaded. Starting consumer.")
    else:
        logger.info("[*] Loading TTS model...")
        await asyncio.to_thread(tts_provider.load)
        logger.info("[*] TTS model loaded. Starting consumer.")

    await queue.consume(handle_tts_message)
    logger.info("[*] Waiting for TTS tasks")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
