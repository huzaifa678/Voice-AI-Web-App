import io
import tempfile
import numpy as np
from pydub import AudioSegment
from silero_vad import get_speech_timestamps, load_silero_vad


class AudioService:
    _model = None

    @classmethod
    def model(cls):
        if cls._model is None:
            from faster_whisper import WhisperModel  
            cls._model = WhisperModel(
                "base",
                device="cpu",
                compute_type="int8" 
            )
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

    @classmethod
    def transcribe_pcm(cls, audio_pcm: bytes, sample_rate: int = 16000):
        audio = (
            np.frombuffer(audio_pcm, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )
        if not VADService.is_speech(audio, sample_rate):
            return None

        model = cls.model()
        segments, _ = model.transcribe(audio)
        return " ".join(seg.text for seg in segments)
    
    @staticmethod
    def verify_phrase(text: str, expected: str) -> bool:
        return expected.lower() in text.lower()

    @classmethod
    def process_audio(cls, audio_pcm: bytes, sample_rate: int = 16000):
        audio = (
            np.frombuffer(audio_pcm, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )

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
        return cls._model

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
            (t["end"] - t["start"]) / sample_rate * 1000
            for t in timestamps
        )

        return duration_ms >= min_speech_ms
