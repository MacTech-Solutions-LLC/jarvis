"""OpenAI provider implementation"""

import httpx
from typing import Optional
from app.core.config import Config
from app.core.openai_errors import raise_for_openai_status

class OpenAIProvider:
    """OpenAI API provider"""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.openai_api_key
        self.base_url = "https://api.openai.com/v1"
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0
        )

    def generate_text(self, prompt: str, model: str = "gpt-4", max_tokens: int = 1000) -> str:
        """Generate text response"""
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }

        response = self.client.post(f"{self.base_url}/chat/completions", json=payload)
        raise_for_openai_status(response)

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()