import json
import base64
from app.common.rabbit_mq import get_channel
from app.audio.services import AudioService
from app.llm.services import LLMService
import asyncio

def callback(ch, method, properties, body):
    """
    Consume audio bytes, transcribe, and query LLM.
    Publish response to 'audio_responses' queue.
    """
    audio_bytes = base64.b64decode(body)
    text = AudioService.process_audio(audio_bytes)
    
    if not text:
        print("No speech detected.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    async def query_llm():
        response = await LLMService.query_from_text_async(
            user_id="worker",
            text=text,
            ip="127.0.0.1",
        )
        payload = {
            "user_id": properties.headers.get("user_id") if properties.headers else "anon",
            "transcript": text,
            "response": response
        }
        channel.basic_publish(
            exchange="",
            routing_key="audio_responses",
            body=json.dumps(payload)
        )

    asyncio.run(query_llm())
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel, _ = get_channel()

channel.queue_declare(queue="audio_tasks", durable=True)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue="audio_tasks", on_message_callback=callback)

print(" [*] Waiting for audio tasks. To exit press CTRL+C")
channel.start_consuming()
