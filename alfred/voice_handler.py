import whisper
from config import WHISPER_MODEL

model = whisper.load_model(WHISPER_MODEL)

def transcribe_voice(audio_path):
    try:
        # fp16=False: CPU can't do half-precision, this silences the warning
        result = model.transcribe(audio_path, fp16=False)
        return result["text"].strip()
    except Exception as e:
        return f"Error transcribing audio: {e}"
