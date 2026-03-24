from __future__ import annotations

import json
from typing import Any

import httpx

from it_doc_builder.config import Settings


class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _resolved_provider(self) -> str:
        return (self._settings.llm_provider or "deepseek").strip().lower()

    def _resolved_api_key(self) -> str:
        return (self._settings.llm_api_key or self._settings.deepseek_api_key or "").strip()

    def _resolved_model(self) -> str:
        provider = self._resolved_provider()
        configured = (self._settings.llm_model or "").strip()
        if configured:
            return configured
        if provider == "openai":
            return "gpt-4o-mini"
        if provider == "groq":
            return "llama-3.3-70b-versatile"
        if provider == "openrouter":
            return "openai/gpt-4o-mini"
        return self._settings.deepseek_model

    def _resolved_base_url(self) -> str:
        provider = self._resolved_provider()
        configured = (self._settings.llm_base_url or "").strip()
        if configured:
            return configured
        if provider == "openai":
            return "https://api.openai.com/v1"
        if provider == "groq":
            return "https://api.groq.com/openai/v1"
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        return self._settings.deepseek_base_url

    async def generate_html(self, prompt: str) -> str:
        if not self._resolved_api_key():
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
        if not self._resolved_api_key():
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
        if not self._resolved_api_key():
            return self._fallback_html(user_prompt)

        url = f"{self._resolved_base_url().rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._resolved_api_key()}",
            "Content-Type": "application/json",
        }
        if self._resolved_provider() == "openrouter":
            headers["HTTP-Referer"] = "https://docagent.local"
            headers["X-Title"] = "DocAgent"
        payload: dict[str, Any] = {
            "model": self._resolved_model(),
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