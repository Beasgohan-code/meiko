"""
Meiko Agent - Provider Abstraction Layer

Every LLM backend (NVIDIA NIM, Google Gemini, OpenRouter, Groq, OpenAI,
local Ollama, etc.) implements this common interface so the harness never
needs to know which vendor is actually answering.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    image_urls: Optional[list[str]] = None  # data: URLs or http(s) URLs for multimodal/vision input


@dataclass
class StreamChunk:
    delta: str = ""
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


@dataclass
class ProviderConfig:
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    pass


class LLMProvider(abc.ABC):
    """Common interface implemented by every model backend."""

    id: str = "base"
    display_name: str = "Base Provider"
    requires_key: bool = True
    default_base_url: str = ""
    free_tier: bool = False

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abc.abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion. Must yield StreamChunk objects."""
        raise NotImplementedError
        yield  # pragma: no cover

    @abc.abstractmethod
    async def list_models(self) -> list[str]:
        raise NotImplementedError

    def is_configured(self) -> bool:
        return bool(self.config.api_key) or not self.requires_key
