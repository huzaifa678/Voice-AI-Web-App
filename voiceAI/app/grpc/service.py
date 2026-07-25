import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import numpy as np
import grpc
from app.audio.services import AudioService, VADService
from app.common.rabbit_mq import publish_audio_task
from app.common.rate_limit import rate_limit
from app.common.logger import get_logger
from app.grpc import audio_pb2, service_pb2_grpc
from django.contrib.auth import get_user_model

from app.models import AudioSession

executor = ThreadPoolExecutor(max_workers=4)
User = get_user_model()
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

logger = get_logger(__name__)


class AudioServicer(service_pb2_grpc.AudioServiceServicer):
    """
    gRPC servicer for streaming audio transcription.
    Works directly with PCM16 bytes sent from the client.
    """

    async def StreamTranscribe(self, request_iterator, context):
        audio_chunks = []
        async for chunk in request_iterator:
            audio_chunks.append(chunk.pcm)

        logger.debug("chunks appended")

        if not audio_chunks:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("No audio received")
            logger.debug("condition false")
            return audio_pb2.TranscriptionResponse(transcript="")

        audio_bytes = b"".join(audio_chunks)

        metadata = dict(context.invocation_metadata())
        user_id = metadata.get("user_id", "anonymous")
        logger.debug("before the running loop")
        await asyncio.get_running_loop().run_in_executor(
            None, rate_limit, f"audio-transcribe:{user_id}", 30, 60
        )

        logger.debug("after the running loop")

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

        if not VADService.is_speech(audio_np, sample_rate=16000):
            logger.debug("condition false 1")
            return audio_pb2.TranscriptionResponse(transcript="")

        loop = asyncio.get_running_loop()
        user = None
        if user_id:
            user = await loop.run_in_executor(
                None, lambda: User.objects.filter(id=user_id).first()
            )

        session = await loop.run_in_executor(
            None, lambda: AudioSession.objects.create(user=user)
        )

        try:
            logger.debug("RATE LIMIT CHECK 1")
            await loop.run_in_executor(
                None,
                rate_limit,
                f"audio-transcribe:{user_id or 'anonymous'}",
                30,
                60,
            )
            logger.debug("RATE LIMIT CHECK 2")

            vad_result = VADService.is_speech(audio_np, sample_rate=16000)
            logger.debug("VAD RESULT: %s", vad_result)

            if not vad_result:
                return audio_pb2.TranscriptionResponse(transcript="")

            await loop.run_in_executor(
                None,
                lambda: AudioSession.objects.filter(id=session.id).update(
                    status=AudioSession.Status.PROCESSING
                ),
            )

            logger.info("STARTING TRANSCRIPTION")

            transcript = await AudioService.transcribe_pcm(audio_bytes, 16000)
            logger.info("STARTING TRANSCRIPTION")

            await loop.run_in_executor(None, session.mark_completed, transcript or "")

            logger.info("ABOUT TO PUBLISH AUDIO TASK")
            await publish_audio_task(
                user_id=str(user.id) if user else None,
                audio_bytes=audio_bytes,
            )
            logger.info("PUBLISHED AUDIO TASK")

            return audio_pb2.TranscriptionResponse(transcript=transcript or "")

        except Exception as e:
            await loop.run_in_executor(None, session.mark_failed, str(e))
            raise
