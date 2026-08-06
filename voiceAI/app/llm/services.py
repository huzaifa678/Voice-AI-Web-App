import httpx

from app.common.logger import get_logger
from app.llm.prompts import build_messages
from app.llm.providers import get_llm_provider

logger = get_logger(__name__)


class LLMService:
    @staticmethod
    async def query_from_text_async(
        text: str,
        max_tokens: int = 256,
    ) -> str:
        provider = get_llm_provider()
        messages = build_messages(text)

        try:
            return await provider.generate(messages, max_tokens=max_tokens)
        except httpx.HTTPStatusError as e:
            logger.error("HTTP status error: %s", e.response.status_code)
            logger.error("Response body: %s", e.response.text)
            return f"HTTP Error {e.response.status_code}"
        except httpx.RequestError as e:
            logger.error("HTTPX request failed: %s", e)
            return ""
