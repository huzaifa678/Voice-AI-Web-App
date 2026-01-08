from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from app.audio.services import AudioService
from app.common.rate_limit import rate_limit
import os

class AudioTranscribeView(APIView):
    """
    Endpoint to receive audio, transcribe it using Whisper,
    and return the text.
    """

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
            return Response({"detail": "Audio file required"}, status=400)

        try:
            wav_path = AudioService.save_audio_to_wav(audio_file.read(), format="webm")
        except Exception as e:
            return Response({"detail": f"Failed to process audio: {str(e)}"}, status=400)

        try:
            text = AudioService.transcribe(wav_path)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

        if not text.strip():
            return Response({"detail": "No speech detected in audio"}, status=400)

        return Response({"transcript": text}, status=200)

