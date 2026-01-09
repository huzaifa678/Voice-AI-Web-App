import asyncio
from concurrent.futures import ThreadPoolExecutor
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import sync_to_async
import os
from app.audio.services import AudioService, VADService
from app.common.rate_limit import rate_limit
from rest_framework.permissions import IsAuthenticated

executor = ThreadPoolExecutor(max_workers=2)


class AudioTranscribeView(APIView):
    """
    Receives raw audio bytes (from WebSocket or other clients),
    converts to WAV temporarily, runs VAD and transcription.
    """
    permission_classes = [IsAuthenticated]

    async def post(self, request):
        rate_limit(
            key=f"audio-transcribe:{request.user.id}",
            limit=30,
            window_seconds=60,
        )

        audio_bytes = request.data.get("audio")
        if not audio_bytes:
            return Response({"detail": "Audio bytes required"}, status=status.HTTP_400_BAD_REQUEST)

        wav_path = await sync_to_async(
            AudioService.save_audio_to_wav,
            thread_sensitive=False
        )(audio_bytes, format="webm")  

        import soundfile as sf
        audio_pcm, sr = sf.read(wav_path, dtype="int16")
        audio_bytes_pcm = audio_pcm.tobytes()

        if not VADService.is_speech(audio_pcm, sample_rate=sr):
            os.remove(wav_path)
            return Response({"detail": "No speech detected"}, status=status.HTTP_400_BAD_REQUEST)

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            executor,
            AudioService.transcribe_pcm,
            audio_bytes_pcm,
            sr
        )

        os.remove(wav_path)

        if not text.strip():
            return Response({"detail": "No speech detected"}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"transcript": text}, status=status.HTTP_200_OK)
