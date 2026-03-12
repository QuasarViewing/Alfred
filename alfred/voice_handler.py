import whisper
import os
import tempfile
model = whisper.load_model("base")

def transcribe_voice(audio_path):
    try:
        result = model.transcribe(audio_path)
        return result["text"].strip()
    except Exception as e:
        return f"Error transcribing audio: {e}"