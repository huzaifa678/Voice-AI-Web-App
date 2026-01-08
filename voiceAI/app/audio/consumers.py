from channels.generic.websocket import AsyncWebsocketConsumer
import json

from .services import AudioService
from app.common.rate_limit import rate_limit

class AudioStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        ip = self.scope["client"][0]
        rate_limit(
            key=f"ws:{ip}",
            limit=10,
            window_seconds=60,
        )
        await self.accept()

    async def receive(self, bytes_data=None):
        if not bytes_data:
            return

        text = AudioService.process_audio(bytes_data)
        if text:
            await self.send(json.dumps({"text": text}))
