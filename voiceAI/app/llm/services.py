import os
from dotenv import load_dotenv
import httpx
from app.common.logger import get_logger

logger = get_logger(__name__)

load_dotenv()


class LLMService:
    API_KEY = os.getenv("GROQ_API_KEY", "")
    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    @staticmethod
    async def query_from_text_async(
        text: str,
        max_tokens: int = 256,
    ) -> str:

        if not LLMService.API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set")

        logger.info("TEXT: %s", text)

        headers = {
            "Authorization": f"Bearer {LLMService.API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": text}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=100.0) as client:
            try:
                resp = await client.post(
                    LLMService.ENDPOINT,
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info("DATA: %s", data)
                return data["choices"][0]["message"]["content"]
            except httpx.RequestError as e:
                logger.error("HTTPX Request failed: %s", e)
            except httpx.HTTPStatusError as e:
                logger.error("HTTP status error: %s", e.response.status_code)
                logger.error("Response headers: %s", e.response.headers)
                logger.error("Response body: %s", e.response.text)
                return f"HTTP Error {e.response.status_code}"
            except Exception as e:
                logger.error("Unexpected error: %s", e)
