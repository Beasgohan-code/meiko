"""
Google Gemini provider (free tier friendly via AI Studio API keys).
Uses the generateContent / streamGenerateContent REST endpoint.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

import httpx

from .base import ChatMessage, LLMProvider, ProviderConfig, ProviderError, StreamChunk


class GeminiProvider(LLMProvider):
    id = "gemini"
    display_name = "Google Gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"
    free_tier = True

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = (config.base_url or self.default_base_url).rstrip("/")

    def _to_contents(self, messages: list[ChatMessage]) -> tuple[Optional[str], list[dict[str, Any]]]:
        system_parts = []
        contents = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        system_instruction = "\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        model_name = model or self.config.model or "gemini-1.5-flash"
        system_instruction, contents = self._to_contents(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self.base_url}/models/{model_name}:streamGenerateContent"
        params = {"key": self.config.api_key, "alt": "sse"}

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                async with client.stream("POST", url, params=params, json=payload) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        raise ProviderError(f"gemini error {resp.status_code}: {body.decode(errors='ignore')[:500]}")
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if not data:
                            continue
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        candidates = obj.get("candidates") or []
                        if not candidates:
                            continue
                        cand = candidates[0]
                        parts = cand.get("content", {}).get("parts", [])
                        # Gemini 2.x "Thinking" models mark internal reasoning parts with
                        # thought: true, distinct from the final answer parts.
                        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                        reasoning = "".join(p.get("text", "") for p in parts if p.get("thought"))
                        finish = cand.get("finishReason")
                        if reasoning:
                            yield StreamChunk(reasoning_delta=reasoning, raw=obj)
                        if text:
                            yield StreamChunk(delta=text, raw=obj)
                        if finish:
                            yield StreamChunk(delta="", finish_reason=finish, raw=obj)
            except httpx.ConnectError as e:
                raise ProviderError(f"Could not connect to Gemini: {e}") from e

    async def list_models(self) -> list[str]:
        url = f"{self.base_url}/models"
        params = {"key": self.config.api_key}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, params=params)
                if resp.status_code >= 400:
                    return []
                data = resp.json()
                return [m.get("name", "").split("/")[-1] for m in data.get("models", [])]
        except Exception:
            return []
