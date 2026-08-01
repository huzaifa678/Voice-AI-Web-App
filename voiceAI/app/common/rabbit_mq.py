import json
import pika
import os
import aio_pika
from app.common.telemetry import SpanKind, current_trace_headers, record_exception, tracer

tracer = tracer(__name__)

_rmq_connection = None

_connection = None
_channel = None

RABBITMQ_URL = os.getenv("RABBITMQ_URL") or os.getenv("CELERY_BROKER_URL")


def get_channel():
    global _connection, _channel

    if _connection and _connection.is_open:
        return _channel, _connection

    params = pika.URLParameters(RABBITMQ_URL)
    _connection = pika.BlockingConnection(params)
    _channel = _connection.channel()
    return _channel, _connection


async def get_persistent_channel():
    global _channel
    if _channel is None or _channel.is_closed:
        conn = await get_connection()
        _channel = await conn.channel()
    return _channel


async def get_connection():
    global _rmq_connection

    if _rmq_connection and not _rmq_connection.is_closed:
        return _rmq_connection

    _rmq_connection = await aio_pika.connect_robust(os.getenv("RABBITMQ_URL"))
    return _rmq_connection


async def publish_audio_task(user_id: str, transcript: str):
    with tracer.start_as_current_span(
        "voice.rabbitmq.publish_audio_task",
        kind=SpanKind.PRODUCER,
        attributes={
            "messaging.system": "rabbitmq",
            "messaging.destination.name": "audio_tasks",
            "voice.transcript_chars": len(transcript or ""),
            "voice.user_id": str(user_id) if user_id else "anonymous",
        },
    ) as span:
        try:
            channel = await get_persistent_channel()

            await channel.declare_queue("audio_tasks", durable=True)

            trace_headers = current_trace_headers()
            payload = {
                "user_id": user_id,
                "transcript": transcript,
                "trace": trace_headers,
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    headers=trace_headers,
                ),
                routing_key="audio_tasks",
            )
        except Exception as exc:
            record_exception(span, exc)
            raise


async def publish_audio_response(
    user_id: str, response: str = None, audio_bytes: str = None
):
    """
    Publishes a processed LLM/audio response to RabbitMQ.
    - user_id: target user
    - response: text from LLM
    - audio_bytes: base64-encoded audio for TTS
    """
    with tracer.start_as_current_span(
        "voice.rabbitmq.publish_audio_response",
        kind=SpanKind.PRODUCER,
        attributes={
            "messaging.system": "rabbitmq",
            "messaging.destination.name": "audio_responses",
            "voice.user_id": str(user_id) if user_id else "anonymous",
            "voice.response_chars": len(response or ""),
            "voice.tts.audio_base64_chars": len(audio_bytes or ""),
        },
    ) as span:
        channel = None
        try:
            connection = await get_connection()
            channel = await connection.channel()

            exchange = await channel.declare_exchange(
                "audio_responses_exchange", aio_pika.ExchangeType.DIRECT, durable=True
            )

            trace_headers = current_trace_headers()
            payload = {"user_id": user_id, "trace": trace_headers}
            if response is not None:
                payload["response"] = response
            if audio_bytes is not None:
                payload["audio_bytes"] = audio_bytes

            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    headers=trace_headers,
                ),
                routing_key="audio_responses",
            )
        except Exception as exc:
            record_exception(span, exc)
            raise
        finally:
            if channel is not None:
                await channel.close()


async def publish_email_task(email_data: dict):
    """Publish an email task into the Celery queue."""

    from app.workers.task_email import send_welcome_email

    send_welcome_email.delay(email_data)


def close_connection():
    global _connection, _channel

    if _channel and _channel.is_open:
        _channel.close()

    if _connection and _connection.is_open:
        _connection.close()

    _channel = None
    _connection = None
