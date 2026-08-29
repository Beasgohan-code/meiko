"""
Generic OpenAI-compatible chat-completions provider.

Works out of the box for: NVIDIA NIM, OpenRouter, Groq, OpenAI, and
local Ollama (which also exposes an OpenAI-compatible /v1 endpoint).
This one class powers most of Meiko's supported model backends.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

import httpx

from .base import ChatMessage, LLMProvider, ProviderConfig, ProviderError, StreamChunk


class OpenAICompatibleProvider(LLMProvider):
    id = "openai_compatible"
    display_name = "OpenAI-Compatible"
    default_base_url = "https://api.openai.com/v1"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = (config.base_url or self.default_base_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _to_payload_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out = []
        for m in messages:
            entry: dict[str, Any] = {"role": m.role}
            if m.image_urls:
                content_parts: list[dict[str, Any]] = [{"type": "text", "text": m.content}]
                for url in m.image_urls:
                    content_parts.append({"type": "image_url", "image_url": {"url": url}})
                entry["content"] = content_parts
            else:
                entry["content"] = m.content
            if m.name:
                entry["name"] = m.name
            if m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                entry["tool_calls"] = m.tool_calls
            out.append(entry)
        return out

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        payload: dict[str, Any] = {
            "model": model or self.config.model,
            "messages": self._to_payload_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"
        tool_call_acc: dict[int, dict[str, Any]] = {}

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                async with client.stream("POST", url, headers=self._headers(), json=payload) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        raise ProviderError(f"{self.id} error {resp.status_code}: {body.decode(errors='ignore')[:500]}")
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta", {})
                        finish = choice.get("finish_reason")
                        content = delta.get("content") or ""
                        tcs = delta.get("tool_calls")
                        if tcs:
                            for tc in tcs:
                                idx = tc.get("index", 0)
                                slot = tool_call_acc.setdefault(idx, {
                                    "id": tc.get("id", f"call_{idx}"),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                })
                                fn = tc.get("function", {})
                                if fn.get("name"):
                                    slot["function"]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    slot["function"]["arguments"] += fn["arguments"]
                        if content:
                            yield StreamChunk(delta=content, raw=obj)
                        if finish:
                            final_tool_calls = list(tool_call_acc.values()) if tool_call_acc else None
                            yield StreamChunk(delta="", tool_calls=final_tool_calls, finish_reason=finish, raw=obj)
            except httpx.ConnectError as e:
                raise ProviderError(f"Could not connect to {self.id} at {self.base_url}: {e}") from e

    async def list_models(self) -> list[str]:
        url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers=self._headers())
                if resp.status_code >= 400:
                    return []
                data = resp.json()
                return [m.get("id") for m in data.get("data", []) if m.get("id")]
        except Exception:
            return []
