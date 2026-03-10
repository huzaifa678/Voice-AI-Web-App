# from TTS.utils.manage import ModelManager

# manager = ModelManager()

# manager.download_model("tts_models/en/ljspeech/tacotron2-DDC")
# manager.download_model("vocoder_models/en/ljspeech/hifigan_v2")
# print(manager.output_prefix)

import os
from TTS.api import TTS
from TTS.utils.manage import ModelManager

model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
model_path = os.path.join(os.getenv("TTS_HOME", os.path.expanduser("~/.local/share/tts")), model_name.replace("/", "--"))

os.makedirs(model_path, exist_ok=True)

with open(os.path.join(model_path, "audiolm_agreement.txt"), "w") as f:
    f.write("I have read and agreed to the CPML terms.")

tts = TTS(model_name)
