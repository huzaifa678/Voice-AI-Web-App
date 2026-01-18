from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from app.audio.services import AudioService, VADService, transcribe_audio_bytes
from app.common.rate_limit import rate_limit
from rest_framework.permissions import IsAuthenticated


class AudioTranscribeView(APIView):
    permission_classes = [IsAuthenticated]

    async def post(self, request):
        rate_limit(
            key=f"audio-transcribe:{request.user.id}",
            limit=30,
            window_seconds=60,
        )

        try:
            result = await transcribe_audio_bytes(
                request.body,
                user_id=str(request.user.id),
            )
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )