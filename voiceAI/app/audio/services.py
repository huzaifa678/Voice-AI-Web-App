from tokenize import generate_tokens
from faster_whisper import WhisperModel
from huggingface_hub import User
import numpy as np
from silero_vad import get_speech_timestamps, load_silero_vad

model = WhisperModel("small", compute_type="int8")

class AudioService:

    @staticmethod
    def transcribe(wav_path):
        segments, _ = model.transcribe(wav_path)
        return " ".join(seg.text for seg in segments)

    @staticmethod
    def verify_phrase(text, expected):
        return expected.lower() in text.lower()
    
    @staticmethod
    def process_audio(audio_pcm: bytes, sample_rate=16000):
        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype("float32") / 32768.0

        if not VADService.is_speech(audio, sample_rate):
            return None  

        segments, _ = model.transcribe(audio)
        return " ".join(seg.text for seg in segments)
    
    
class VADService:
    _model = None

    @classmethod
    def model(cls):
        if cls._model is None:
            cls._model = load_silero_vad()
        return cls._model

    @staticmethod
    def is_speech(
        audio: np.ndarray,
        sample_rate: int = 16000,
        min_speech_ms: int = 300,
    ) -> bool:
        """
        audio: float32 numpy array (-1..1)
        """
        timestamps = get_speech_timestamps(
            audio,
            VADService.model(),
            sampling_rate=sample_rate,
        )

        if not timestamps:
            return False

        duration_ms = sum(
            (t["end"] - t["start"]) / sample_rate * 1000
            for t in timestamps
        )

        return duration_ms >= min_speech_ms