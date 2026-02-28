import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
import os
import tempfile
import numpy as np
from pydub import AudioSegment
from silero_vad import get_speech_timestamps, load_silero_vad
from app.common.rabbit_mq import publish_audio_task

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

executor = ThreadPoolExecutor(max_workers=2)


async def transcribe_audio_bytes(audio_bytes: bytes, user_id: str):
    if not audio_bytes:
        raise ValueError("Audio bytes required")

    print("enter the service body2")

    wav_path = await asyncio.to_thread(
        AudioService.save_audio_to_wav, audio_bytes, format="webm"
    )

    print("enter the service body3")

    try:
        import soundfile as sf

        audio_pcm, sr = sf.read(wav_path, dtype="int16")
        audio_bytes_pcm = audio_pcm.tobytes()

        if not VADService.is_speech(audio_pcm, sample_rate=sr):
            raise ValueError("No speech detected")

        print("enter the service body4")

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            executor, AudioService.transcribe_pcm, audio_bytes_pcm, sr
        )

        if not text.strip():
            raise ValueError("Empty transcription")

        publish_audio_task(
            user_id=user_id,
            audio_bytes=audio_bytes,
        )

        return {"transcript": text}

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


class AudioService:
    _model = None
    MODEL_PATH = "/app/models/base"

    @classmethod
    def model(cls):
        if cls._model is None:
            print("[AudioService] Loading Whisper model...")
            from faster_whisper import WhisperModel

            if ENVIRONMENT == "local":
                cls._model = WhisperModel("Base", device="cpu", compute_type="int8")
            else:
                cls._model = WhisperModel(
                    cls.MODEL_PATH, device="cpu", compute_type="int8"
                )
                print("[AudioService] Whisper model loaded.")
        return cls._model

    @staticmethod
    def save_audio_to_wav(audio_bytes: bytes, format: str = "webm") -> str:
        """
        Converts raw audio bytes to a temporary WAV file
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=format)
            audio = audio.set_channels(1).set_frame_rate(16000)
            audio.export(tmp.name, format="wav")
            return tmp.name

    @classmethod
    def transcribe(cls, wav_path: str) -> str:
        model = cls.model()
        segments, _ = model.transcribe(wav_path)
        return " ".join(seg.text for seg in segments)

    # @classmethod
    # def transcribe_pcm(cls, audio_pcm: bytes, sample_rate: int = 16000):
    #     audio = (
    #         np.frombuffer(audio_pcm, dtype=np.int16)
    #         .astype(np.float32) / 32768.0
    #     )
    #     if not VADService.is_speech(audio, sample_rate):
    #         return None

    #     model = cls.model()
    #     segments, _ = model.transcribe(audio)
    #     return " ".join(seg.text for seg in segments)

    @classmethod
    async def transcribe_pcm(
        cls, audio_pcm: bytes, sample_rate: int = 16000, timeout: float = 30.0
    ):
        """
        Kubernetes async/executor version
        """
        if ENVIRONMENT == "local":
            audio = (
                np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
            )
            if not VADService.is_speech(audio, sample_rate):
                return None
            model = cls.model()
            segments, _ = model.transcribe(audio)
            return " ".join(seg.text for seg in segments)

        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if not VADService.is_speech(audio, sample_rate):
            print("[AudioService] No speech detected by VAD")
            return None

        model = cls.model()
        loop = asyncio.get_running_loop()

        def run_transcription():
            print("[AudioService] Whisper transcription started...")
            segments, _ = model.transcribe(audio)
            print("[AudioService] Whisper transcription finished.")
            return segments

        try:
            segments = await asyncio.wait_for(
                loop.run_in_executor(executor, run_transcription), timeout
            )
        except asyncio.TimeoutError:
            print("[AudioService] Whisper transcription TIMEOUT")
            return None
        except Exception as e:
            print(f"[AudioService] Whisper transcription ERROR: {e}")
            return None

        transcript = " ".join(seg.text for seg in segments)
        return transcript

    @staticmethod
    def verify_phrase(text: str, expected: str) -> bool:
        return expected.lower() in text.lower()

    @classmethod
    def process_audio(cls, audio_pcm: bytes, sample_rate: int = 16000):
        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0

        if not VADService.is_speech(audio, sample_rate):
            return None

        model = cls.model()
        segments, _ = model.transcribe(audio)
        return " ".join(seg.text for seg in segments)


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

        print("timestamps", timestamps)

        if not timestamps:
            print("returning false")
            return False

        duration_ms = sum(
            (t["end"] - t["start"]) / sample_rate * 1000 for t in timestamps
        )

        return duration_ms >= min_speech_ms
