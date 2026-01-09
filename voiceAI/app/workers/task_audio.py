from app.common.rabbit_mq import channel
from app.audio.services import AudioService
from app.llm.services import LLMService
import asyncio

def callback(ch, method, properties, body):
    """
    Consume audio bytes, transcribe, and optionally query LLM
    """
    text = AudioService.process_audio(body)
    
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
        print("LLM response:", response)

    asyncio.run(query_llm())

    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue="audio_tasks", on_message_callback=callback)

print(" [*] Waiting for messages. To exit press CTRL+C")
channel.start_consuming()
