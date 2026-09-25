import logging
import tempfile
import soundfile as sf
import kokoro_onnx
import re
import emoji
from config import KOKORO_MODEL_PATH, KOKORO_VOICES_PATH

kokoro = kokoro_onnx.Kokoro(str(KOKORO_MODEL_PATH), str(KOKORO_VOICES_PATH))

def clean_for_speech(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = emoji.replace_emoji(text, replace='')
    text = re.sub(r':00\s*(am|pm|AM|PM)', r' \1', text)
    text = re.sub(r'https?://\S+', 'the link', text)
    return text.strip()

def speak(text):
    try:
        text = clean_for_speech(text)
        if not text:
            return None
        samples, sample_rate = kokoro.create(text, voice="bm_george", speed=1.0, lang="en-us")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, samples, sample_rate)
        return tmp_path
    except Exception as e:
        logging.error(f"Error in TTS: {e}")
        return None
