ARG PLATFORM=linux/amd64
FROM --platform=$PLATFORM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc g++ python3-dev libffi-dev pkg-config \
    libavcodec-dev libavformat-dev libavutil-dev libswresample-dev libswscale-dev \
    git curl rustc cargo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt .

RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements-docker.txt -w /wheels

FROM --platform=$PLATFORM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libmecab-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

COPY . .

RUN mkdir -p /root/.local/share/tts

COPY models /app/models

COPY .env.docker /app/.env.docker

RUN chmod 600 /app/.env.docker && \
    chmod +x voiceAI/*.sh

EXPOSE 8000