import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from app.audio.services import AudioService
from app.common.rabbit_mq import publish_audio_task
from app.common.rate_limit import rate_limit
from app.common.logger import get_logger
from app.common.telemetry import SpanKind, context_from_metadata, record_exception, tracer
from app.grpc import audio_pb2, service_pb2_grpc
from django.contrib.auth import get_user_model

from app.models import AudioSession

executor = ThreadPoolExecutor(max_workers=8)
User = get_user_model()
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

logger = get_logger(__name__)
tracer = tracer(__name__)

ROLLING_BUFFER_MIN_BYTES = int(16000 * 2 * 2)


class AudioServicer(
    service_pb2_grpc.AudioServiceServicer
):

    async def StreamTranscribe(
        self,
        request_iterator,
        context
    ):
        metadata = tuple(context.invocation_metadata())
        parent_context = context_from_metadata(metadata)

        with tracer.start_as_current_span(
            "voice.grpc.stream_transcribe",
            context=parent_context,
            kind=SpanKind.SERVER,
        ) as span:
            audio_chunks = []
            transcript_parts = []

            try:
                async for chunk in request_iterator:

                    audio_chunks.append(
                        chunk.pcm
                    )

                    span.add_event(
                        "voice.grpc.chunk_received",
                        {"voice.chunk_bytes": len(chunk.pcm)},
                    )

                    transcript = await self._run_transcription(
                        chunk.pcm
                    )

                    if transcript:

                        transcript_parts.append(
                            transcript
                        )

                        # streaming response
                        yield audio_pb2.TranscriptionResponse(
                            transcript=transcript
                        )

                    await asyncio.sleep(0)

                final_transcript = " ".join(
                    transcript_parts
                )

                span.set_attribute("voice.grpc.chunk_count", len(audio_chunks))
                span.set_attribute("voice.transcript_chars", len(final_transcript))
                span.set_attribute(
                    "voice.audio_bytes",
                    sum(len(chunk) for chunk in audio_chunks),
                )

                await self._finalize_session(
                    context,
                    audio_chunks,
                    final_transcript
                )

            except Exception as e:
                record_exception(span, e)
                raise

    async def _run_transcription(
        self,
        audio_bytes
    ):
        """
        Process one PCM chunk.

        SimulStreaming keeps internal
        decoding state.
        """

        with tracer.start_as_current_span(
            "voice.stt.simul_whisper",
            attributes={"voice.audio_bytes": len(audio_bytes)},
        ):
            try:

                transcript = await AudioService.transcribe_pcm(
                    audio_bytes,
                    16000
                )

                return transcript or ""

            except Exception:

                logger.exception(
                    "SimulStreaming transcription failed"
                )

                return ""

    async def _finalize_session(
        self,
        context,
        audio_chunks,
        transcript
    ):
        """
        Same optimization path:
        - DB async
        - fire and forget RabbitMQ
        """

        metadata = dict(
            context.invocation_metadata()
        )

        user_id = metadata.get(
            "user_id",
            "anonymous"
        )

        try:
            with tracer.start_as_current_span(
                "voice.grpc.rate_limit",
                attributes={"voice.user_id": str(user_id)},
            ):
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    rate_limit,
                    f"audio-transcribe:{user_id}",
                    30,
                    60
                )

        except Exception:

            logger.warning(
                "Rate limit check failed for %s",
                user_id
            )

        loop = asyncio.get_running_loop()

        user = None

        if user_id:

            user = await loop.run_in_executor(
                None,
                lambda: User.objects.filter(
                    id=user_id
                ).first()
            )

        with tracer.start_as_current_span(
            "voice.grpc.finalize_session",
            attributes={
                "voice.user_id": str(user_id),
                "voice.transcript_chars": len(transcript or ""),
            },
        ):
            session = await loop.run_in_executor(
                None,
                lambda: AudioSession.objects.create(
                    user=user
                )
            )

            try:

                await loop.run_in_executor(
                    None,
                    lambda: AudioSession.objects.filter(
                        id=session.id
                    ).update(
                        status=AudioSession.Status.PROCESSING
                    )
                )

                await loop.run_in_executor(
                    None,
                    session.mark_completed,
                    transcript
                )

                asyncio.create_task(
                    publish_audio_task(
                        user_id=str(user.id)
                        if user
                        else None,

                        transcript=transcript,
                    )
                )

            except Exception as e:

                await loop.run_in_executor(
                    None,
                    session.mark_failed,
                    str(e)
                )

                logger.exception(
                    "Session finalization failed"
                )
