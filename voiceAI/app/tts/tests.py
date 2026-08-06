import io
import wave

import numpy as np
from unittest.mock import MagicMock, patch

from app.tts.providers import get_tts_provider
from app.tts.services import BaseTTSService, PiperTTSService, TTSService


def test_services_implement_base_interface():
    assert issubclass(TTSService, BaseTTSService)
    assert issubclass(PiperTTSService, BaseTTSService)
    for engine in (TTSService, PiperTTSService):
        assert callable(getattr(engine, "load", None))
        assert callable(getattr(engine, "synthesize", None))


def test_get_tts_provider_local_returns_piper(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    assert get_tts_provider() is PiperTTSService


def test_get_tts_provider_non_local_returns_xtts(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    assert get_tts_provider() is TTSService


def test_chunk_text_respects_max_chars():
    text = " ".join(["word"] * 100)
    chunks = TTSService.chunk_text(text, max_chars=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 40 for chunk in chunks)


def test_piper_synthesize_returns_wav_bytes():
    PiperTTSService._voice = None

    def fake_synthesize_wav(text, wav_file, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 100)

    fake_voice = MagicMock()
    fake_voice.synthesize_wav.side_effect = fake_synthesize_wav

    with patch("piper.PiperVoice.load", return_value=fake_voice):
        data = PiperTTSService.synthesize("hello world")

    fake_voice.synthesize_wav.assert_called_once()
    with wave.open(io.BytesIO(data)) as wav_file:
        assert wav_file.getframerate() == 22050
        assert wav_file.getnframes() > 0

    PiperTTSService._voice = None


def test_xtts_synthesize_returns_wav_bytes():
    inner = MagicMock()
    inner.inference.return_value = {"wav": np.zeros(2000, dtype=np.float32)}
    model = MagicMock()
    model.synthesizer.tts_model = inner

    with patch.object(TTSService, "_tts_model", model), \
            patch.object(TTSService, "_gpt_cond_latent", MagicMock()), \
            patch.object(TTSService, "_speaker_embedding", MagicMock()):
        result = TTSService.synthesize("Hello there. How are you?")

    assert isinstance(result, bytes)
    assert len(result) > 0
    assert inner.inference.called


def test_xtts_synthesize_skips_chunk_on_index_error():
    inner = MagicMock()
    inner.inference.side_effect = IndexError("index out of range in self")
    model = MagicMock()
    model.synthesizer.tts_model = inner

    with patch.object(TTSService, "_tts_model", model), \
            patch.object(TTSService, "_gpt_cond_latent", MagicMock()), \
            patch.object(TTSService, "_speaker_embedding", MagicMock()):
        result = TTSService.synthesize("Hello there.")

    assert result == b""
    assert inner.inference.called
