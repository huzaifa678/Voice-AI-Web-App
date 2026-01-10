import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import httpx
from app.common.rabbit_mq import get_channel
from app.audio.services import VADService
from app.common.rate_limit import rate_limit
import numpy as np


class AudioStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        ip = self.scope["client"][0]
        rate_limit(
            key=f"ws:{ip}",
            limit=30,
            window_seconds=60,
        )
        self.audio_buffer = b""
        await self.accept()

    async def receive(self, bytes_data=None):
        """
        Recieves audio bytes from the client, buffers them and calls the view for processing.
        """
        if not bytes_data:
            return

        self.audio_buffer += bytes_data

        audio_np = (
            np.frombuffer(self.audio_buffer, dtype=np.int16)
            .astype("float32") / 32768.0
        )

        if not VADService.is_speech(audio_np):
            return

        try:
            response = await self.send_to_view(self.audio_buffer)
        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e)}))
            self.audio_buffer = b""
            return

        await self.send(text_data=json.dumps(response))

        self.audio_buffer = b""

    async def send_to_view(self, audio_bytes):
        """
        Send buffered audio to the transcription view via internal API call.
        """
        auth_header = dict(self.scope["headers"]).get(b'authorization', b'').decode()
        token = auth_header.split("Bearer ")[-1] if "Bearer " in auth_header else ""

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8000/api/audio/transcribe/",
                headers={"Authorization": f"Bearer {token}"},
                content=audio_bytes
            )
            resp.raise_for_status()
            return resp.json()
        
    async def listen_llm_responses(self):
        """
        Consume LLM responses from 'audio_responses' and forward to this client
        """
        connection = get_channel()
        channel = connection.channel()
        channel.queue_declare(queue="audio_responses")

        def callback(ch, method, body):
            data = json.loads(body)
            if data.get("user_id") == self.user_id:
                asyncio.run_coroutine_threadsafe(
                    self.send(text_data=json.dumps(data)), asyncio.get_event_loop()
                )
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue="audio_responses", on_message_callback=callback)
        print(f"Listening for LLM responses for user {self.user_id}")
        channel.start_consuming()
