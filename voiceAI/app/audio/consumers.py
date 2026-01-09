from channels.generic.websocket import AsyncWebsocketConsumer
import json
from app.common.rabbit_mq import publish_audio_task
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

        publish_audio_task(
            user_id=str(self.scope.get("user", {}).get("id", "anon")),
            audio_bytes=bytes_data
        )

        await self.send(text_data=json.dumps({"status": "queued"}))