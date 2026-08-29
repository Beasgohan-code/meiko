"""
Provider Registry - central place describing every supported model backend
and how to instantiate it. This is what powers the Settings UI in the web
app / mobile app (list of providers, whether a free tier exists, whether a
key is required, default base URLs, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.config import Settings
from .base import LLMProvider, ProviderConfig
from .gemini import GeminiProvider
from .openai_compatible import OpenAICompatibleProvider


@dataclass
class ProviderMeta:
    id: str
    display_name: str
    default_base_url: str
    default_model: str
    requires_key: bool
    free_tier: bool
    key_help_url: str
    description: str


PROVIDER_CATALOG: list[ProviderMeta] = [
    ProviderMeta(
        id="nvidia",
        display_name="NVIDIA NIM",
        default_base_url="https://integrate.api.nvidia.com/v1",
        default_model="meta/llama-3.3-70b-instruct",
        requires_key=True,
        free_tier=True,
        key_help_url="https://build.nvidia.com/",
        description="Free NVIDIA-hosted open models (Llama, DeepSeek, Mistral, Qwen and more) via build.nvidia.com API keys.",
    ),
    ProviderMeta(
        id="gemini",
        display_name="Google Gemini",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-1.5-flash",
        requires_key=True,
        free_tier=True,
        key_help_url="https://aistudio.google.com/apikey",
        description="Google AI Studio free tier - Gemini 1.5 Flash/Pro models.",
    ),
    ProviderMeta(
        id="openrouter",
        display_name="OpenRouter",
        default_base_url="https://openrouter.ai/api/v1",
        default_model="meta-llama/llama-3.1-8b-instruct:free",
        requires_key=True,
        free_tier=True,
        key_help_url="https://openrouter.ai/keys",
        description="Aggregator with many free-tier open models (Llama, Mistral, DeepSeek, Qwen).",
    ),
    ProviderMeta(
        id="groq",
        display_name="Groq",
        default_base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.1-8b-instant",
        requires_key=True,
        free_tier=True,
        key_help_url="https://console.groq.com/keys",
        description="Ultra-fast free-tier inference for open models (Llama, Gemma, Mixtral).",
    ),
    ProviderMeta(
        id="openai",
        display_name="OpenAI",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        requires_key=True,
        free_tier=False,
        key_help_url="https://platform.openai.com/api-keys",
        description="OpenAI GPT models (paid).",
    ),
    ProviderMeta(
        id="ollama",
        display_name="Ollama (Local)",
        default_base_url="http://localhost:11434/v1",
        default_model="llama3.1",
        requires_key=False,
        free_tier=True,
        key_help_url="https://ollama.com/download",
        description="Run fully local/offline open-weight models on your own machine.",
    ),
    ProviderMeta(
        id="cerebras",
        display_name="Cerebras",
        default_base_url="https://api.cerebras.ai/v1",
        default_model="llama-3.3-70b",
        requires_key=True,
        free_tier=True,
        key_help_url="https://cloud.cerebras.ai/",
        description="Extremely fast free-tier inference for Llama models on Cerebras wafer-scale chips.",
    ),
    ProviderMeta(
        id="huggingface",
        display_name="Hugging Face Inference",
        default_base_url="https://router.huggingface.co/v1",
        default_model="meta-llama/Llama-3.3-70B-Instruct",
        requires_key=True,
        free_tier=True,
        key_help_url="https://huggingface.co/settings/tokens",
        description="Free-tier serverless inference across many open-weight models via Hugging Face's router.",
    ),
    ProviderMeta(
        id="mistral",
        display_name="Mistral (La Plateforme)",
        default_base_url="https://api.mistral.ai/v1",
        default_model="mistral-small-latest",
        requires_key=True,
        free_tier=True,
        key_help_url="https://console.mistral.ai/api-keys",
        description="Mistral's free experimental tier for their open-weight models.",
    ),
]

_CATALOG_BY_ID = {p.id: p for p in PROVIDER_CATALOG}


def get_provider_meta(provider_id: str) -> Optional[ProviderMeta]:
    return _CATALOG_BY_ID.get(provider_id)


def list_provider_meta() -> list[ProviderMeta]:
    return PROVIDER_CATALOG


def build_provider(
    provider_id: str,
    settings: Settings,
    *,
    override_api_key: Optional[str] = None,
    override_base_url: Optional[str] = None,
    override_model: Optional[str] = None,
) -> LLMProvider:
    """Instantiate a provider by id, merging env defaults with any
    runtime overrides (e.g. keys the user typed into Settings UI)."""
    meta = get_provider_meta(provider_id)
    if meta is None:
        raise ValueError(f"Unknown provider: {provider_id}")

    env_key_map = {
        "nvidia": settings.NVIDIA_API_KEY,
        "gemini": settings.GEMINI_API_KEY,
        "openrouter": settings.OPENROUTER_API_KEY,
        "groq": settings.GROQ_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "ollama": None,
        "cerebras": getattr(settings, "CEREBRAS_API_KEY", None),
        "huggingface": getattr(settings, "HUGGINGFACE_API_KEY", None),
        "mistral": getattr(settings, "MISTRAL_API_KEY", None),
    }
    env_base_map = {
        "nvidia": settings.NVIDIA_BASE_URL,
        "gemini": settings.GEMINI_BASE_URL,
        "openrouter": settings.OPENROUTER_BASE_URL,
        "groq": settings.GROQ_BASE_URL,
        "openai": settings.OPENAI_BASE_URL,
        "ollama": settings.OLLAMA_BASE_URL.rstrip("/") + "/v1",
        "cerebras": "https://api.cerebras.ai/v1",
        "huggingface": "https://router.huggingface.co/v1",
        "mistral": "https://api.mistral.ai/v1",
    }

    api_key = override_api_key or env_key_map.get(provider_id)
    base_url = override_base_url or env_base_map.get(provider_id) or meta.default_base_url
    model = override_model or (settings.DEFAULT_MODEL if provider_id == settings.DEFAULT_PROVIDER else meta.default_model)

    config = ProviderConfig(api_key=api_key, base_url=base_url, model=model)

    if provider_id == "gemini":
        return GeminiProvider(config)
    # nvidia / openrouter / groq / openai / ollama all speak OpenAI-compatible API
    return OpenAICompatibleProvider(config)
