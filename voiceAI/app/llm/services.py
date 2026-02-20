import os
from dotenv import load_dotenv
import httpx
import os
import httpx


import logging
logger = logging.getLogger(__name__)

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
        
        print("TEXT", text)

        headers = {
            "Authorization": f"Bearer {LLMService.API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "user", "content": text}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2
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
                print("HTTPX Request failed:", e)
            except httpx.HTTPStatusError as e:
                print("HTTP status error:", e.response.status_code)
                print("Response headers:", e.response.headers)
                print("Response body:", e.response.text)
                return f"HTTP Error {e.response.status_code}"
            except Exception as e:
                print("Unexpected error:", e)
