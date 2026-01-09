import json
import os
import pika


def get_channel():
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    if not rabbitmq_url:
        raise RuntimeError("RABBITMQ_URL is not set")

    params = pika.URLParameters(rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return channel, connection


def publish_audio_task(user_id: str, audio_bytes: bytes):
    channel, _ = get_channel()
    
    payload = {
        "user_id": user_id,
        "audio_bytes": audio_bytes,
    }
    
    channel.basic_publish(
        exchange="",
        routing_key="audio_tasks",
        body=json.dumps(payload),
    )
    
def publish_email_task(email_data: dict):
    channel, _ = get_channel()
    import json
    channel.basic_publish(
        exchange="",
        routing_key="email_tasks",
        body=json.dumps(email_data),
        properties=pika.BasicProperties(delivery_mode=2),  
    )

def close_connection():
    _, connection = get_channel()
    if connection and connection.is_open:
        connection.close()