import base64
import json
import pika
import os
import aio_pika

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


async def publish_audio_task(user_id: str, audio_bytes: bytes):
    """Publish an audio task into the Celery queue."""

    from app.workers.task_audio import process_audio_task

    process_audio_task.delay(user_id, base64.b64encode(audio_bytes).decode())


async def publish_audio_response(
    user_id: str, response: str = None, audio_bytes: str = None
):
    """
    Publishes a processed LLM/audio response to RabbitMQ.
    - user_id: target user
    - response: text from LLM
    - audio_bytes: base64-encoded audio for TTS
    """
    connection = await get_connection()
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        "audio_responses_exchange", aio_pika.ExchangeType.DIRECT, durable=True
    )

    payload = {"user_id": user_id}
    if response is not None:
        payload["response"] = response
    if audio_bytes is not None:
        payload["audio_bytes"] = audio_bytes

    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key="audio_responses",
    )

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
