import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
import os
import tempfile
import numpy as np
from pydub import AudioSegment
from silero_vad import get_speech_timestamps, load_silero_vad
from app.common.rabbit_mq import publish_audio_task
from app.common.logger import get_logger
from app.common.telemetry import record_exception, tracer
from app.audio.simul_whisper_service import SimulWhisperService

logger = get_logger(__name__)
tracer = tracer(__name__)

executor = ThreadPoolExecutor(max_workers=2)


async def transcribe_audio_bytes(audio_bytes: bytes, user_id: str):
    if not audio_bytes:
        raise ValueError("Audio bytes required")

    with tracer.start_as_current_span(
        "voice.audio.transcribe_upload",
        attributes={
            "voice.user_id": str(user_id),
            "voice.audio_bytes": len(audio_bytes),
        },
    ) as span:
        try:
            logger.debug("enter the service body2")

            with tracer.start_as_current_span("voice.audio.convert_to_wav"):
                wav_path = await asyncio.to_thread(
                    AudioService.save_audio_to_wav, audio_bytes, format="webm"
                )

            logger.debug("enter the service body3")

            try:
                import soundfile as sf

                audio_pcm, sr = sf.read(wav_path, dtype="int16")
                audio_bytes_pcm = audio_pcm.tobytes()
                span.set_attribute("voice.sample_rate", sr)
                span.set_attribute("voice.pcm_bytes", len(audio_bytes_pcm))

                with tracer.start_as_current_span("voice.vad.verify_speech"):
                    if not VADService.is_speech(audio_pcm, sample_rate=sr):
                        raise ValueError("No speech detected")

                logger.debug("enter the service body4")

                text = await AudioService.transcribe_pcm(audio_bytes_pcm, sr)
                span.set_attribute("voice.transcript_chars", len(text or ""))

                if not text.strip():
                    raise ValueError("Empty transcription")

                await publish_audio_task(
                    user_id=user_id,
                    transcript=text,
                )

                return {"transcript": text}

            finally:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
        except Exception as exc:
            record_exception(span, exc)
            raise


class AudioService:

    @staticmethod
    def save_audio_to_wav(
        audio_bytes: bytes,
        format: str = "webm"
    ) -> str:
        """
        Converts audio bytes into 16khz mono wav.
        """

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as tmp:

            audio = AudioSegment.from_file(
                io.BytesIO(audio_bytes),
                format=format
            )

            audio = (
                audio
                .set_channels(1)
                .set_frame_rate(16000)
            )

            audio.export(
                tmp.name,
                format="wav"
            )

            return tmp.name

    @classmethod
    def transcribe(
        cls,
        wav_path: str
    ):

        import soundfile as sf

        audio, sr = sf.read(
            wav_path,
            dtype="float32"
        )

        audio = np.asarray(
            audio
        )

        return cls.transcribe_numpy(
            audio,
            sr
        )

    @classmethod
    def transcribe_numpy(
        cls,
        audio: np.ndarray,
        sample_rate: int = 16000
    ):
        """
        Sends numpy audio chunk to SimulStreaming.
        """

        with tracer.start_as_current_span(
            "voice.stt.transcribe_numpy",
            attributes={
                "voice.sample_rate": sample_rate,
                "voice.audio_samples": len(audio),
            },
        ):
            transcript = (
                SimulWhisperService.transcribe_chunk(
                    audio
                )
            )

        if not transcript:
            return ""

        return transcript

    @classmethod
    async def transcribe_pcm(
        cls,
        audio_pcm: bytes,
        sample_rate: int = 16000,
        timeout: float = 30.0
    ):
        """
        gRPC streaming entrypoint.

        Receives PCM16 chunks,
        converts to float32,
        sends to SimulStreaming.
        """

        audio = (
            np.frombuffer(
                audio_pcm,
                dtype=np.int16
            )
            .astype(np.float32)
            /
            32768.0
        )

        loop = asyncio.get_running_loop()

        try:

            with tracer.start_as_current_span(
                "voice.stt.transcribe_pcm",
                attributes={
                    "voice.sample_rate": sample_rate,
                    "voice.pcm_bytes": len(audio_pcm),
                    "voice.timeout_seconds": timeout,
                },
            ) as span:
                transcript = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        cls.transcribe_numpy,
                        audio,
                        sample_rate
                    ),
                    timeout
                )
                span.set_attribute("voice.transcript_chars", len(transcript or ""))

            return transcript

        except asyncio.TimeoutError:

            logger.warning(
                "[AudioService] SimulStreaming timeout"
            )

            return ""

        except Exception as e:

            logger.exception(
                "[AudioService] SimulStreaming failed: %s",
                e
            )

            return ""

    @staticmethod
    def verify_phrase(
        text: str,
        expected: str
    ) -> bool:

        return (
            expected.lower()
            in
            text.lower()
        )

    @classmethod
    async def process_audio(
        cls,
        audio_pcm: bytes,
        sample_rate: int = 16000
    ):

        return await cls.transcribe_pcm(
            audio_pcm,
            sample_rate
        )


class VADService:
    _model = None

    @classmethod
    def model(cls):
        if cls._model is None:
            cls._model = load_silero_vad()
            cls._model.eval()
        return cls._model

    @staticmethod
    def speech_prob(audio: np.ndarray, sample_rate=16000) -> float:
        import torch

        frame = torch.from_numpy(audio).unsqueeze(0)

        with torch.no_grad():
            prob = VADService.model()(frame, sample_rate).item()

        return prob

    @staticmethod
    def is_speech(
        audio: np.ndarray,
        sample_rate: int = 16000,
        min_speech_ms: int = 500,
    ) -> bool:

        timestamps = get_speech_timestamps(
            audio,
            VADService.model(),
            sampling_rate=sample_rate,
        )

        logger.debug("timestamps: %s", timestamps)

        if not timestamps:
            logger.debug("returning false")
            return False

        duration_ms = sum(
            (t["end"] - t["start"]) / sample_rate * 1000 for t in timestamps
        )

        return duration_ms >= min_speech_ms
