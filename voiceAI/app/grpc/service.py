import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import grpc
from app.audio.services import AudioService, VADService
from app.common.rabbit_mq import publish_audio_task
from app.common.rate_limit import rate_limit
from app.grpc import audio_pb2, service_pb2_grpc
from django.contrib.auth import get_user_model

from app.models import AudioSession

executor = ThreadPoolExecutor(max_workers=4)
User = get_user_model()


class AudioServicer(service_pb2_grpc.AudioServiceServicer):
    """
    gRPC servicer for streaming audio transcription.
    Works directly with PCM16 bytes sent from the client.
    """

    async def StreamTranscribe(self, request_iterator, context):
        audio_chunks = []
        async for chunk in request_iterator:
            audio_chunks.append(chunk.pcm)
            
        print("chunks appended")

        if not audio_chunks:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("No audio received")
            print("condition false")
            return audio_pb2.TranscriptionResponse(transcript="")

        audio_bytes = b"".join(audio_chunks)

        metadata = dict(context.invocation_metadata())
        user_id = metadata.get("user_id", "anonymous")
        print("before the running loop")
        await asyncio.get_running_loop().run_in_executor(
            None, rate_limit, f"audio-transcribe:{user_id}", 30, 60
        )
        
        print("after the running loop")

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

        if not VADService.is_speech(audio_np, sample_rate=16000):
            print("condition false 1")
            return audio_pb2.TranscriptionResponse(transcript="")

        loop = asyncio.get_running_loop()
        user = None
        if user_id:
            user = await loop.run_in_executor(
                None,
                lambda: User.objects.filter(id=user_id).first()
            )

        session = await loop.run_in_executor(
            None,
            lambda: AudioSession.objects.create(user=user)
        )

        try:
            await loop.run_in_executor(
                None,
                rate_limit,
                f"audio-transcribe:{user_id or 'anonymous'}",
                30,
                60,
            )

            if not VADService.is_speech(audio_np, sample_rate=16000):
                session.mark_completed("")
                return audio_pb2.TranscriptionResponse(transcript="")

            await loop.run_in_executor(
                None,
                lambda: AudioSession.objects.filter(id=session.id)
                .update(status=AudioSession.Status.PROCESSING)
            )

            transcript = await loop.run_in_executor(
                executor,
                AudioService.transcribe_pcm,
                audio_bytes,
                16000
            )

            await loop.run_in_executor(
                None,
                session.mark_completed,
                transcript or ""
            )

            await publish_audio_task(
                user_id=str(user.id) if user else None,
                audio_bytes=audio_bytes,
                session_id=str(session.id),
            )

            return audio_pb2.TranscriptionResponse(
                transcript=transcript or ""
            )

        except Exception as e:
            await loop.run_in_executor(
                None,
                session.mark_failed,
                str(e)
            )
            raise