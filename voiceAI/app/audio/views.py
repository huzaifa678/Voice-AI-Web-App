from concurrent.futures import ThreadPoolExecutor
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import os

from app.audio.services import AudioService
from app.common import rate_limit

executor = ThreadPoolExecutor(max_workers=2)  

class AudioTranscribeView(APIView):

    def post(self, request):
        user_id = request.user.id if request.user.is_authenticated else None
        ip = request.META.get("REMOTE_ADDR", "unknown")

        rate_limit(
            key=f"audio-transcribe:{user_id or ip}",
            limit=20,
            window_seconds=60,
        )

        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response(
                {"detail": "Audio file required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            wav_path = AudioService.save_audio_to_wav(
                audio_file.read(),
                format="webm",
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to process audio: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            future = executor.submit(AudioService.transcribe, wav_path)
            text = future.result()
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

        if not text.strip():
            return Response(
                {"detail": "No speech detected in audio"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"transcript": text},
            status=status.HTTP_200_OK,
        )


