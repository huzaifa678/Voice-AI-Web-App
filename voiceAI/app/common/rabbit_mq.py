import base64
import json
import pika
import os
import aio_pika

_rmq_connection = None

_connection = None
_channel = None

def get_channel():
    global _connection, _channel

    if _connection and _connection.is_open:
        return _channel, _connection

    params = pika.URLParameters(os.getenv("RABBITMQ_URL"))
    _connection = pika.BlockingConnection(params)
    _channel = _connection.channel()
    return _channel, _connection

async def get_connection():
    global _rmq_connection

    if _rmq_connection and not _rmq_connection.is_closed:
        return _rmq_connection

    _rmq_connection = await aio_pika.connect_robust(
        os.getenv("RABBITMQ_URL")
    )
    return _rmq_connection



async def publish_audio_task(user_id: str, audio_bytes: bytes):
    connection = await get_connection()
    channel = await connection.channel()

    await channel.declare_queue("audio_tasks", durable=True)

    payload = {
        "user_id": user_id,
        "audio_bytes": base64.b64encode(audio_bytes).decode(),
    }

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key="audio_tasks",
    )

    await channel.close()
    
async def publish_audio_response(user_id: str, response: str):
    """
    Publishes a processed LLM/audio response to RabbitMQ.
    Ensures the queue and exchange exist, and publishes a persistent message.
    """
    connection = await get_connection()
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        "audio_responses_exchange",
        aio_pika.ExchangeType.DIRECT,
        durable=True
    )

    payload = {
        "user_id": user_id,
        "response": response
    }

    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
        ),
        routing_key="audio_responses"
    )

    await channel.close()

async def publish_email_task(email_data: dict):
    connection = await get_connection()
    channel = await connection.channel()

    await channel.declare_queue("email_tasks", durable=True)

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(email_data).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key="email_tasks",
    )

    await channel.close()


def close_connection():
    global _connection, _channel

    if _channel and _channel.is_open:
        _channel.close()

    if _connection and _connection.is_open:
        _connection.close()

    _channel = None
    _connection = None
