from app.common.config import config
from app.tts.services import BaseTTSService, PiperTTSService, TTSService


def get_tts_provider() -> type[BaseTTSService]:
    if config.ENVIRONMENT == "local":
        return PiperTTSService
    return TTSService
