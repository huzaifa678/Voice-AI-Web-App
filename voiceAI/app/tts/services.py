import io
import os
import re
import threading
import numpy as np
import torch
import soundfile as sf
from TTS.api import TTS
from TTS.tts.configs.xtts_config import XttsArgs, XttsAudioConfig, XttsConfig
from TTS.config.shared_configs import BaseDatasetConfig

torch.set_num_threads(2)
torch.set_num_interop_threads(1)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_PATH = "/app/models/xtts/tts_models--multilingual--multi-dataset--xtts_v2"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPEAKER_WAV = os.path.join(BASE_DIR, "speaker.wav")


class TTSService:
    _tts_model = None
    _speaker_embedding = None
    _gpt_cond_latent = None
    _model_lock = threading.Lock()
    _loading_thread = None

    @staticmethod
    def _load_model_sync():
        """Actual blocking model load"""
        torch.serialization.add_safe_globals(
            [XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs]
        )
        os.environ["COQUI_TOS_AGREED"] = "1"

        if ENVIRONMENT == "local":
            TTSService._tts_model = TTS(
                model_name=XTTS_MODEL_NAME,
                progress_bar=False,
                gpu=torch.cuda.is_available(),
            )
        else:
            TTSService._tts_model = TTS(
                model_path=XTTS_PATH,
                config_path=f"{XTTS_PATH}/config.json",
                progress_bar=False,
                gpu=torch.cuda.is_available(),
            )

        model = TTSService._tts_model.synthesizer.tts_model.to(DEVICE)

        with torch.no_grad():
            TTSService._gpt_cond_latent, TTSService._speaker_embedding = model.get_conditioning_latents(SPEAKER_WAV)

        if DEVICE == "cuda":
            model = model.half()
            TTSService._gpt_cond_latent = TTSService._gpt_cond_latent.half()
            TTSService._speaker_embedding = TTSService._speaker_embedding.half()

        model.eval()

    @staticmethod
    def load_model(async_load=False):
        """Load XTTS model once, optionally asynchronously"""
        if TTSService._tts_model is not None:
            return TTSService._tts_model

        if async_load:
            if TTSService._loading_thread is None:
                TTSService._loading_thread = threading.Thread(target=TTSService._load_model_sync)
                TTSService._loading_thread.start()
            return None  
        else:
            with TTSService._model_lock:
                if TTSService._tts_model is None:
                    TTSService._load_model_sync()
            return TTSService._tts_model

    @staticmethod
    def chunk_text(text, max_chars=200):
        words = text.split()
        chunks = []
        current = []
        for word in words:
            current.append(word)
            if len(" ".join(current)) > max_chars:
                chunks.append(" ".join(current[:-1]))
                current = [word]
        if current:
            chunks.append(" ".join(current))
        return chunks

    @staticmethod
    def synthesize(text: str, language="en", sample_rate=24000) -> bytes:
        if TTSService._tts_model is None:
            raise RuntimeError("TTS model is not loaded yet")

        model = TTSService._tts_model.synthesizer.tts_model

        sentences = re.split(r"(?<=[.!?]) +", text)
        chunks = sum([TTSService.chunk_text(s) for s in sentences], [])

        all_wavs = []
        for chunk in chunks:
            if not chunk.strip():
                continue
            with torch.inference_mode(), torch.autocast("cuda" if DEVICE=="cuda" else "cpu"):
                result = model.inference(
                    chunk,
                    language,
                    TTSService._gpt_cond_latent,
                    TTSService._speaker_embedding,
                )
            all_wavs.append(np.array(result["wav"], dtype=np.float32))

        if not all_wavs:
            return b""

        combined = np.concatenate(all_wavs)
        wav_int16 = (combined * 32767).astype(np.int16)
        buffer = io.BytesIO()
        sf.write(buffer, wav_int16, samplerate=sample_rate, format="WAV", subtype="PCM_16")
        buffer.seek(0)
        return buffer.read()