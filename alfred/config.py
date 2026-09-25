"""
Central settings for Alfred.

Every path is built from BASE_DIR (the folder this file lives in),
so Alfred works no matter which folder you run it from — including
inside a Docker container.
"""
from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Claude
CLAUDE_MODEL = os.getenv("ALFRED_MODEL", "claude-sonnet-4-6")

# Data (DATA_DIR can be moved, e.g. to a Docker volume)
DATA_DIR = Path(os.getenv("ALFRED_DATA_DIR", BASE_DIR))
DB_PATH = DATA_DIR / "alfred.db"
CHROMA_PATH = DATA_DIR / "chroma_db"
LOG_PATH = DATA_DIR / "alfred.log"
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"
SCREENSHOT_DIR = DATA_DIR / "screenshots"

# Google OAuth
GOOGLE_CREDENTIALS_PATH = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", BASE_DIR / "credentials.json"))
GOOGLE_TOKEN_PATH = Path(os.getenv("GOOGLE_TOKEN_PATH", DATA_DIR / "token.json"))

# Voice models
MODELS_DIR = Path(os.getenv("ALFRED_MODELS_DIR", BASE_DIR))
KOKORO_MODEL_PATH = MODELS_DIR / "kokoro-v1_0.onnx"
KOKORO_VOICES_PATH = MODELS_DIR / "voices-v1_0.bin"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
VOICE_REPLIES = os.getenv("ALFRED_VOICE_REPLIES", "true").lower() == "true"

# Location and time
TIMEZONE = "Pacific/Auckland"
HOME_LOCATION = os.getenv("ALFRED_HOME_LOCATION", "Taupo, New Zealand")

# Banking (Phase 2, read-only)
AKAHU_APP_TOKEN = os.getenv("AKAHU_APP_TOKEN")
AKAHU_USER_TOKEN = os.getenv("AKAHU_USER_TOKEN")

# Food ordering safety (Milestone 8)
ORDER_DRY_RUN = os.getenv("ALFRED_ORDER_DRY_RUN", "true").lower() == "true"
ORDER_MAX_NZD = float(os.getenv("ALFRED_ORDER_MAX_NZD", "60"))
