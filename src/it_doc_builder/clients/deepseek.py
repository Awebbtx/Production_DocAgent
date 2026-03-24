from __future__ import annotations

import json
from typing import Any

import httpx

from it_doc_builder.config import Settings


class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_html(self, prompt: str) -> str:
        if not self._settings.deepseek_api_key:
            return self._fallback_html(prompt)

        return await self.complete(
            system_prompt=(
                "You convert IT department notes into structured HTML suitable for a formal report. "
                "Return body-only semantic HTML and do not include markdown fences."
            ),
            user_prompt=prompt,
            temperature=0.2,
        )

    async def recommend_templates(self, prompt: str) -> str:
        if not self._settings.deepseek_api_key:
            return json.dumps([])

        return await self.complete(
            system_prompt=(
                "You classify messy IT project notes into the best matching documentation templates. "
                "Return only a JSON array with exactly three objects. "
                "Each object must contain rank, document_type, confidence, and rationale."
            ),
            user_prompt=prompt,
            temperature=0.1,
        )

    async def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if not self._settings.deepseek_api_key:
            return self._fallback_html(user_prompt)

        url = f"{self._settings.deepseek_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._settings.deepseek_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _fallback_html(prompt: str) -> str:
        escaped_prompt = (
            prompt.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            "<section>"
            "<h2>Draft Output</h2>"
            "<p>No DeepSeek API key is configured, so this is a local placeholder result.</p>"
            f"<pre>{escaped_prompt}</pre>"
            "</section>"
        )