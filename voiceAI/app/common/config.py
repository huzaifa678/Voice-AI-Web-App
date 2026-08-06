import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
    DJANGO_TEST = os.getenv("DJANGO_TEST") == "true"
    IS_CI = os.getenv("CI") == "true"
    APP_VERSION = os.getenv("APP_VERSION", "latest")

    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "pgbouncer")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", 6432)

    GOOGLE_USER_EMAIL = os.getenv("GOOGLE_USER_EMAIL", "")
    GOOGLE_APP_PASSWORD = os.getenv("GOOGLE_APP_PASSWORD", "")

    RABBITMQ_URL = os.getenv("RABBITMQ_URL") or os.getenv("CELERY_BROKER_URL")
    REDIS_URL = os.getenv("REDIS_URL") or os.getenv("CELERY_RESULT_BACKEND")
    CELERY_BROKER_URL = RABBITMQ_URL or "amqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND = REDIS_URL or "redis://localhost:6379/0"

    REFRESH_TOKEN_LIFETIME = os.getenv("REFRESH_TOKEN_LIFETIME", "7d")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
    LLM_BASE_URL = os.getenv("LLM_BASE_URL")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY") or GROQ_API_KEY

    OTEL_SDK_DISABLED = os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true"
    OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "voice-ai-backend")
    OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:43170")
    OTEL_CONSOLE_EXPORTER = os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true"

    LOG_FILE = os.getenv("LOG_FILE")

    WHISPER_MODEL_PATH = os.getenv("WHISPER_MODEL_PATH")
    WHISPER_MODEL_PATH_DEFAULT_LOCAL = "/app/models/small.en.pt"
    WHISPER_MODEL_PATH_DEFAULT_REMOTE = "/app/models/whisper/large-v3.pt"
    WHISPER_MIN_CHUNK = float(os.getenv("WHISPER_MIN_CHUNK", "2.0"))

    PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH")

    VAD_DEBUG = os.getenv("VAD_DEBUG", "false").lower() == "true"
    GRPC_DEPLOYMENT_TYPE = os.getenv("GRPC_DEPLOYMENT_TYPE", "local").lower()


config = Config()
