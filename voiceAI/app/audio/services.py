import io
import tempfile
from tokenize import generate_tokens
from faster_whisper import WhisperModel
from pydub import AudioSegment
from huggingface_hub import User
import numpy as np
from silero_vad import get_speech_timestamps, load_silero_vad

model = WhisperModel("small", compute_type="int8")

class AudioService:
    
    @staticmethod
    def save_audio_to_wav(audio_bytes: bytes, format: str = "webm") -> str:
        """
        Converts raw audio bytes to a temporary WAV file
        Returns the path to the WAV file
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=format)
            audio = audio.set_channels(1).set_frame_rate(16000)  # mono 16kHz
            audio.export(tmp.name, format="wav")
            return tmp.name

    @staticmethod
    def transcribe(wav_path):
        segments, _ = model.transcribe(wav_path)
        return " ".join(seg.text for seg in segments)
    
    @staticmethod
    def transcribe_pcm(audio_pcm: bytes, sample_rate=16000):
        """
        Transcribe raw PCM bytes (from mic)
        """
        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype("float32") / 32768.0

        if not VADService.is_speech(audio, sample_rate):
            return None

        segments, _ = model.transcribe(audio)
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