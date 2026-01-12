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
        self.user_id = getattr(self.scope.get("user"), "id", None)
        
        print("Connecting user_id:", self.user_id)
        
        if self.user_id is None:
            await self.close(code=4401)  
            return
        
        self.in_speech = False
        self.last_speech_ts = None
        self.silence_timeout = 0.6  
        
        rate_limit(
            key=f"ws:{ip}",
            limit=30,
            window_seconds=60,
        )
        
        self.audio_buffer = b""
        await self.accept()
        
        asyncio.create_task(self.listen_llm_responses())

    async def receive(self, text_data=None, bytes_data=None):
        """
        Recieves audio bytes from the client, buffers them and calls the view for processing.
        """
        
        if not bytes_data:
            print("No bytes received")
            return
            
        self.audio_buffer += bytes_data
        
        min_bytes = int(16000 * 1.0 * 2) 

        if len(self.audio_buffer) < min_bytes:
            return 
        
        audio_np = (
            np.frombuffer(self.audio_buffer, dtype=np.int16)
            .astype("float32") / 32768.0
        )

        is_speech = VADService.is_speech(audio_np)

        now = asyncio.get_event_loop().time()

        if is_speech:
            self.audio_buffer += bytes_data
            self.in_speech = True
            self.last_speech_ts = now
            print("returning")
            return
        
        
        
        print("is_speech", is_speech)
        
        if self.in_speech:
            print("inside in speech")
            if now - self.last_speech_ts > self.silence_timeout:
                await self.process_buffer()
                self.audio_buffer = b""
                self.in_speech = False
                print("awaited")
        
        print("done")

        try:
            response = await self.send_to_view(self.audio_buffer)
            print("SENT")
        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e)}))
            self.audio_buffer = b""
            return

        await self.send(text_data=json.dumps(response))

        self.audio_buffer = b""
        
    async def process_buffer(self):
        if len(self.audio_buffer) < 16000 * 2 * 0.5:
            return

        try:
            response = await self.send_to_view(self.audio_buffer)
            await self.send(text_data=json.dumps(response))
        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e)}))


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
        channel, _ = get_channel()
        channel.queue_declare(queue="audio_responses")

        async def async_callback(body):
            data = json.loads(body)
            if data.get("user_id") == self.user_id:
                await self.send(text_data=json.dumps(data))

        def callback(ch, method, body):
            asyncio.create_task(async_callback(body))
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue="audio_responses", on_message_callback=callback)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, channel.start_consuming)
        
    async def disconnect(self, code):
        print(f"Disconnecting user {self.user_id}, code: {code}")
        if hasattr(self, "audio_buffer"):
            self.audio_buffer = b""
            
    async def cleanup(self):
        pass
