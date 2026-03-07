import io
import os
import re
import numpy as np
from TTS.api import TTS
import soundfile as sf

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
MODEL_PATH = ""


class TTSService:
    MODEL_PATH = "app/models/tts_models--en--ljspeech--tacotron2-DDC"
    VCODER_MODEL_PATH = "app/models/vocoder_models--en--ljspeech--hifigan_v2"

    if ENVIRONMENT == "local":
        tts_model = TTS(
            model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False
        )
    else:
        tts_model = TTS(
            model_path=MODEL_PATH, vocoder_path=VCODER_MODEL_PATH, progress_bar=False
        )

    @staticmethod
    def synthesize(text: str, sample_rate: int = 22050) -> bytes:
        sentences = re.split(r"(?<=[.!?]) +", text)
        all_wavs = []

        for s in sentences:
            if not s.strip():
                continue

            wav = TTSService.tts_model.tts(s, speaker=None)
            all_wavs.append(np.array(wav, dtype=np.float32))

        combined_wav = np.concatenate(all_wavs)

        wav_int16 = (combined_wav * 32767).astype(np.int16)

        buffer = io.BytesIO()
        sf.write(
            buffer, wav_int16, samplerate=sample_rate, format="WAV", subtype="PCM_16"
        )
        buffer.seek(0)

        return buffer.read()
