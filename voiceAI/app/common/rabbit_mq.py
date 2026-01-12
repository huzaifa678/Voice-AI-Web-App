import base64
import json
import pika
import os

_connection = None
_channel = None

def get_channel():
    global _connection, _channel

    if _connection and _connection.is_open:
        return _channel, _connection

    rabbitmq_url = os.getenv("RABBITMQ_URL")
    params = pika.URLParameters(rabbitmq_url)
    _connection = pika.BlockingConnection(params)
    _channel = _connection.channel()
    return _channel, _connection


def publish_audio_task(user_id: str, audio_bytes: bytes):
    channel, _ = get_channel()
    channel.queue_declare(queue="audio_tasks", durable=True)
    payload = {
        "user_id": user_id,
        "audio_bytes": base64.b64encode(audio_bytes).decode()
    }
    
    channel.basic_publish(
        exchange="",
        routing_key="audio_tasks",
        body=json.dumps(payload),
    )
    
def publish_email_task(email_data: dict):
    channel, _ = get_channel()
    channel.queue_declare(queue="email_tasks", durable=True)
    print(f"Publishing email task: {email_data}") 
    import json
    channel.basic_publish(
        exchange="",
        routing_key="email_tasks",
        body=json.dumps(email_data),
        properties=pika.BasicProperties(delivery_mode=2),  
    )

def close_connection():
    global _connection, _channel

    if _channel and _channel.is_open:
        _channel.close()

    if _connection and _connection.is_open:
        _connection.close()

    _channel = None
    _connection = None
