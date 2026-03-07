FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libffi-dev \
    pkg-config \
    libmecab-dev \
    git \
    curl \
    rustc \
    cargo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel \
    && pip wheel --no-cache-dir -r requirements.txt -w /wheels

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*

COPY . .

RUN mkdir -p /root/.local/share/tts

COPY models /app/models

COPY .env.docker /app/.env.docker
RUN chmod 600 /app/.env.docker

RUN chmod +x voiceAI/start.sh \
    && chmod +x voiceAI/k8s-start.sh \
    && chmod +x voiceAI/wait-for-it.sh \
    && chmod +x voiceAI/grpc-start.sh

EXPOSE 8000