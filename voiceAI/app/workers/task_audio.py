import asyncio
import base64
import json
import aio_pika

from app.audio.services import AudioService
from app.llm.services import LLMService
from app.common.rabbit_mq import get_connection, publish_audio_response 

async def handle_message(message: aio_pika.IncomingMessage):
    payload = json.loads(message.body)

    try:
        audio_bytes = base64.b64decode(payload["audio_bytes"])
        
        print("inside the handle message method")

        text = await asyncio.to_thread(
            AudioService.process_audio,
            audio_bytes
        )

        if not text.strip():
            await message.ack()
            return

        response = await LLMService.query_from_text_async(text=text)
        
        print("LLM response: ", response)

        await publish_audio_response(
            user_id=payload.get("user_id"),
            response=response
        )

        await message.ack()

    except Exception as e:
        await message.nack(requeue=False)
        raise
    
async def main():
    connection = await get_connection()
    channel = await connection.channel()
    queue = await channel.declare_queue("audio_tasks", durable=True)

    await queue.consume(handle_message)
    
    print("[*] Waiting for email tasks")
    print(" Press CTRL + C to exit")
    await asyncio.Future()  

if __name__ == "__main__":
    asyncio.run(main())
