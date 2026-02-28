from faster_whisper import convert_model

convert_model("openai/whisper-base", output_dir="./models/base")
# ct2-transformers-converter --model openai/whisper-base --output_dir ./models/base --quantization float16
