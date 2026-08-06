from typing import Protocol

import httpx

from app.common.config import config
from app.common.logger import get_logger

logger = get_logger(__name__)

PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "together": "https://api.together.xyz/v1",
    "fireworks": "https://api.fireworks.ai/inference/v1",
    "ollama": "http://localhost:11434/v1",
}


class LLMProvider(Protocol):
    async def generate(
        self,
        messages: list,
        *,
        max_tokens: int = 256,
        temperature: float = 0.2,
    ) -> str:
        ...


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def generate(
        self,
        messages: list,
        *,
        max_tokens: int = 256,
        temperature: float = 0.2,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("LLM API key is not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=100.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


def get_llm_provider() -> LLMProvider:
    provider = config.LLM_PROVIDER
    base_url = config.LLM_BASE_URL or PROVIDER_BASE_URLS.get(provider)
    if not base_url:
        raise RuntimeError(
            f"Unknown LLM provider '{provider}'; set LLM_BASE_URL explicitly"
        )
    model = config.LLM_MODEL
    api_key = config.LLM_API_KEY
    return OpenAICompatibleProvider(base_url=base_url, api_key=api_key, model=model)
