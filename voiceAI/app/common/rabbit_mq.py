import os
import pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

params = pika.URLParameters(RABBITMQ_URL)
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue="audio_tasks", durable=True)


def publish_audio_task(user_id: str, audio_bytes: bytes):
    channel.basic_publish(
        exchange="",
        routing_key="audio_tasks",
        body=audio_bytes,
        properties=pika.BasicProperties(
            delivery_mode=2,  
        ),
    )
    
def publish_email_task(email_data: dict):
    import json
    channel.basic_publish(
        exchange="",
        routing_key="email_tasks",
        body=json.dumps(email_data),
        properties=pika.BasicProperties(delivery_mode=2),  
    )

def close_connection():
    if connection and connection.is_open:
        connection.close()