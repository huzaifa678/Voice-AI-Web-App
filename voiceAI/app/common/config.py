import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name, default="false"):
    return os.getenv(name, default).lower() == "true"


class Config:
    @property
    def ENVIRONMENT(self):
        return os.getenv("ENVIRONMENT", "local")

    @property
    def ALLOWED_HOSTS(self):
        return os.getenv("ALLOWED_HOSTS", "*").split(",")

    @property
    def DJANGO_TEST(self):
        return os.getenv("DJANGO_TEST") == "true"

    @property
    def IS_CI(self):
        return os.getenv("CI") == "true"

    @property
    def APP_VERSION(self):
        return os.getenv("APP_VERSION", "latest")

    @property
    def POSTGRES_HOST(self):
        return os.getenv("POSTGRES_HOST", "pgbouncer")

    @property
    def POSTGRES_PORT(self):
        return os.getenv("POSTGRES_PORT", 6432)

    @property
    def GOOGLE_USER_EMAIL(self):
        return os.getenv("GOOGLE_USER_EMAIL", "")

    @property
    def GOOGLE_APP_PASSWORD(self):
        return os.getenv("GOOGLE_APP_PASSWORD", "")

    @property
    def RABBITMQ_URL(self):
        return os.getenv("RABBITMQ_URL") or os.getenv("CELERY_BROKER_URL")

    @property
    def REDIS_URL(self):
        return os.getenv("REDIS_URL") or os.getenv("CELERY_RESULT_BACKEND")

    @property
    def CELERY_BROKER_URL(self):
        return self.RABBITMQ_URL or "amqp://guest:guest@localhost:5672//"

    @property
    def CELERY_RESULT_BACKEND(self):
        return self.REDIS_URL or "redis://localhost:6379/0"

    @property
    def REFRESH_TOKEN_LIFETIME(self):
        return os.getenv("REFRESH_TOKEN_LIFETIME", "7d")

    @property
    def LLM_PROVIDER(self):
        return os.getenv("LLM_PROVIDER", "groq").lower()

    @property
    def LLM_BASE_URL(self):
        return os.getenv("LLM_BASE_URL")

    @property
    def LLM_MODEL(self):
        return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    @property
    def GROQ_API_KEY(self):
        return os.getenv("GROQ_API_KEY", "")

    @property
    def LLM_API_KEY(self):
        return os.getenv("LLM_API_KEY") or self.GROQ_API_KEY

    @property
    def LLM_CB_FAIL_MAX(self):
        return int(os.getenv("LLM_CB_FAIL_MAX", "5"))

    @property
    def LLM_CB_RESET_TIMEOUT(self):
        return float(os.getenv("LLM_CB_RESET_TIMEOUT", "30"))

    @property
    def OTEL_SDK_DISABLED(self):
        return _bool("OTEL_SDK_DISABLED")

    @property
    def OTEL_SERVICE_NAME(self):
        return os.getenv("OTEL_SERVICE_NAME", "voice-ai-backend")

    @property
    def OTEL_EXPORTER_OTLP_ENDPOINT(self):
        return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:43170")

    @property
    def OTEL_CONSOLE_EXPORTER(self):
        return _bool("OTEL_CONSOLE_EXPORTER")

    @property
    def LOG_FILE(self):
        return os.getenv("LOG_FILE")

    @property
    def WHISPER_MODEL_PATH(self):
        return os.getenv("WHISPER_MODEL_PATH")

    @property
    def WHISPER_MODEL_PATH_DEFAULT_LOCAL(self):
        return "/app/models/small.en.pt"

    @property
    def WHISPER_MODEL_PATH_DEFAULT_REMOTE(self):
        return "/app/models/whisper/large-v3.pt"

    @property
    def WHISPER_MIN_CHUNK(self):
        return float(os.getenv("WHISPER_MIN_CHUNK", "2.0"))

    @property
    def PIPER_MODEL_PATH(self):
        return os.getenv("PIPER_MODEL_PATH")

    @property
    def VAD_DEBUG(self):
        return _bool("VAD_DEBUG")

    @property
    def GRPC_DEPLOYMENT_TYPE(self):
        return os.getenv("GRPC_DEPLOYMENT_TYPE", "local").lower()


config = Config()
