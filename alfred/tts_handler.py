import os
import tempfile
import soundfile as sf
import kokoro_onnx
import re
import emoji

kokoro = kokoro_onnx.Kokoro("kokoro-v1_0.onnx", "voices-v1_0.bin")

def speak(text):
    try:
        text = re.sub(r'<[^>]+>', '', text)
        text = emoji.replace_emoji(text, replace='')
        text = re.sub(r':00\s*(am|pm|AM|PM)', r' \1', text)
        samples, sample_rate = kokoro.create(text, voice="bm_george", speed=1.0, lang="en-us")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, samples, sample_rate)
        return tmp_path
    except Exception as e:
        print(f"Error in TTS: {e}")
        return None
