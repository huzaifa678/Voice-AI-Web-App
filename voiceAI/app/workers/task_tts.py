import asyncio
import base64
import json
import os
import time  # <-- add this
import aio_pika
from app.common.rabbit_mq import get_connection, publish_audio_response
from app.tts.services import TTSService

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")


async def handle_tts_message(message: aio_pika.IncomingMessage):
    payload = json.loads(message.body)
    text = payload["text"]
    user_id = payload["user_id"]

    try:
        print("inside the handle tts message method")

        start_time = time.time()  # start timer
        # Synthesize audio in a thread (blocks TTS CPU/GPU work here)
        audio_bytes = await asyncio.to_thread(TTSService.synthesize, text)
        end_time = time.time()  # end timer

        print(
            f"TTS synthesis took {end_time - start_time:.2f} seconds for text length {len(text)}"
        )

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        print("Audio bytes synthesized, publishing response")

        await publish_audio_response(user_id=user_id, audio_bytes=audio_b64)

        print("Audio response published")

        await message.ack()

    except Exception as e:
        await message.nack(requeue=False)
        raise e


async def main():
    connection = await get_connection()
    channel = await connection.channel()

    queue = await channel.declare_queue("tts_tasks", durable=True)

    if ENVIRONMENT != "local":
        print("[*] Loading XTTS Model into GPU...")
        await asyncio.to_thread(TTSService.load_model, async_load=False)
        print("[*] Model Loaded. Starting consumer.")

    await queue.consume(handle_tts_message)
    print("[*] Waiting for TTS tasks")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
