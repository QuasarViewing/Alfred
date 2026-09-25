# Alfred — one container, everything inside.
# Build:  docker compose build
# Run:    docker compose up -d
FROM python:3.13-slim

# ffmpeg: Whisper needs it to decode Telegram's .ogg voice notes
# libsndfile1: soundfile needs it to write Kokoro's .wav output
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first. The default PyPI torch bundles ~2GB of CUDA
# libraries that are useless without an NVIDIA GPU.
RUN pip install --no-cache-dir torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu

# Requirements before code: Docker caches this layer, so editing a .py
# file doesn't trigger a full reinstall on the next build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium + its system libraries for food ordering (Milestone 8)
RUN playwright install --with-deps chromium

COPY . .

# Data and models live outside the image (see docker-compose.yml)
ENV ALFRED_DATA_DIR=/data \
    ALFRED_MODELS_DIR=/models \
    GOOGLE_CREDENTIALS_PATH=/data/credentials.json \
    GOOGLE_TOKEN_PATH=/data/token.json \
    PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
