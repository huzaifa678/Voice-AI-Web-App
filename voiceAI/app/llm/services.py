import os
from dotenv import load_dotenv
import httpx

load_dotenv()

class LLMService:
    API_KEY = os.getenv("GROQ_API_KEY")
    ENDPOINT = "https://api.groq.ai/v1/completions"  

    @staticmethod
    async def query_from_text_async(
        user_id,
        text: str,
        ip: str,
        prompt_template: str = None,
        max_tokens: int = 200,
    ) -> str:
        """
        Send text to LLM and return response asynchronously.
        You can provide a custom prompt_template to guide the model.
        """
        if prompt_template:
            prompt = prompt_template.replace("{text}", text)
        else:
            prompt = text

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {LLMService.API_KEY}"}
            payload = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "model": "llama-70b-verastile",  
            }
            resp = await client.post(LLMService.ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("text", "")
 