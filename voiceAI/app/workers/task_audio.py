import asyncio
import json
import aio_pika
from app.llm.services import LLMService
from app.common.rabbit_mq import get_connection, publish_audio_response
from app.common.logger import get_logger
from app.common.telemetry import context_from_metadata, current_trace_headers, record_exception, setup_telemetry, tracer

setup_telemetry("voice-ai-audio-worker")
logger = get_logger(__name__)
tracer = tracer(__name__)


async def handle_message(message: aio_pika.IncomingMessage):
    logger.info("RAW MESSAGE RECEIVED: %s", message.body)
    payload = json.loads(message.body)
    parent_context = context_from_metadata(payload.get("trace", {}).items())

    with tracer.start_as_current_span(
        "voice.worker.audio_message",
        context=parent_context,
    ) as span:
        try:
            logger.info("inside the handle message method")

            text = payload.get("transcript")

            if text is None:
                logger.info("No transcript in payload")
                await message.ack()
                return

            text = text.strip()
            span.set_attribute("voice.transcript_chars", len(text))

            if text == "":
                logger.info("Speech-to-text returned empty string")
                await message.ack()
                return

            with tracer.start_as_current_span("voice.llm.query") as llm_span:
                response = await LLMService.query_from_text_async(text=text)
                llm_span.set_attribute("voice.llm.response_chars", len(response or ""))

            logger.info("LLM response: %s", response)
            logger.info("Length of TTS payload text: %s", len(response))

            await publish_audio_response(user_id=payload.get("user_id"), response=response)

            connection = await get_connection()
            channel = await connection.channel()

            tts_payload = {
                "text": response,
                "user_id": payload.get("user_id"),
                "trace": current_trace_headers(),
            }
            tts_message = aio_pika.Message(
                body=json.dumps(tts_payload).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers=current_trace_headers(),
            )

            logger.info(
                "Publishing TTS payload: %s",
                json.dumps({"text": response, "user_id": payload.get("user_id")}),
            )
            logger.info("Publishing TTS message: %s", tts_message)

            await channel.default_exchange.publish(
                tts_message,
                routing_key="tts_tasks",
            )
            logger.info("TTS task published")

            await channel.close()

            await message.ack()

        except Exception as e:
            record_exception(span, e)
            await message.nack(requeue=False)
            raise e


async def main():
    connection = await get_connection()
    channel = await connection.channel()
    queue = await channel.declare_queue("audio_tasks", durable=True)
    await channel.declare_queue("tts_tasks", durable=True)

    await queue.consume(handle_message)

    logger.info("[*] Waiting for audio tasks")
    logger.info(" Press CTRL + C to exit")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
