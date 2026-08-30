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
        default_model="mistralai/mistral-nemotron",
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
    ProviderMeta(
        id="modelscope",
        display_name="ModelScope",
        default_base_url="https://api-inference.modelscope.cn/v1",
        default_model="deepseek-ai/DeepSeek-V4-Pro",
        requires_key=True,
        free_tier=True,
        key_help_url="https://modelscope.cn/my/myaccesstoken",
        description="Alibaba ModelScope's free-tier hosted inference — 50+ open models incl. DeepSeek V4, Qwen3.5, MiniMax M3.",
    ),
    ProviderMeta(
        id="cloudflare",
        display_name="Cloudflare Workers AI",
        default_base_url="https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        default_model="@cf/meta/llama-3.1-8b-instruct",
        requires_key=True,
        free_tier=True,
        key_help_url="https://dash.cloudflare.com/profile/api-tokens",
        description="Cloudflare's free, no-credit-card-required Workers AI tier. Base URL needs your account id (paste as `accountid:apitoken` in the key field).",
    ),
    ProviderMeta(
        id="llm7",
        display_name="LLM7.io",
        default_base_url="https://api.llm7.io/v1",
        default_model="codestral-latest",
        requires_key=False,
        free_tier=True,
        key_help_url="https://token.llm7.io",
        description="Keyless free aggregator — 'turbo' tier models (Codestral, GPT-OSS, Llama 3.1, MiniMax) work with zero signup; a free token from token.llm7.io unlocks the larger 'pro' tier models (Claude/DeepSeek/GPT-5 proxies) and higher limits.",
    ),
    ProviderMeta(
        id="ovhcloud",
        display_name="OVHcloud AI Endpoints",
        default_base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        default_model="Meta-Llama-3_3-70B-Instruct",
        requires_key=True,
        free_tier=True,
        key_help_url="https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/",
        description="OVHcloud's free-tier EU-hosted inference endpoints (Llama, Mistral, Qwen, gpt-oss and more).",
    ),
    ProviderMeta(
        id="sambanova",
        display_name="SambaNova Cloud",
        default_base_url="https://api.sambanova.ai/v1",
        default_model="Meta-Llama-3.3-70B-Instruct",
        requires_key=True,
        free_tier=True,
        key_help_url="https://cloud.sambanova.ai/apis",
        description="SambaNova's free-tier wafer-scale inference — very fast Llama/DeepSeek/Qwen serving.",
    ),
    ProviderMeta(
        id="cohere",
        display_name="Cohere",
        default_base_url="https://api.cohere.ai/compatibility/v1",
        default_model="command-r7b-12-2024",
        requires_key=True,
        free_tier=True,
        key_help_url="https://dashboard.cohere.com/api-keys",
        description="Cohere's free trial-key tier via their OpenAI-compatible endpoint (Command R family).",
    ),
    ProviderMeta(
        id="custom",
        display_name="Custom (OpenAI-compatible)",
        default_base_url="",
        default_model="",
        requires_key=True,
        free_tier=False,
        key_help_url="",
        description=(
            "Bring your own OpenAI-compatible endpoint: paste any base URL + API key "
            "(Anthropic-via-proxy, a self-hosted vLLM/LiteLLM/text-generation-inference "
            "server, a corporate gateway, or any other provider not listed above)."
        ),
    ),
]

_CATALOG_BY_ID = {p.id: p for p in PROVIDER_CATALOG}


def get_provider_meta(provider_id: str) -> Optional[ProviderMeta]:
    return _CATALOG_BY_ID.get(provider_id)


def list_provider_meta() -> list[ProviderMeta]:
    return PROVIDER_CATALOG


# Ordered fallback preference per primary provider: if the primary fails
# (rate-limited, retired model, connection error), Meiko tries these next,
# provided the user has a key configured for them (or they're keyless/local).
_ALL_FALLBACKS = [
    "groq", "nvidia", "cerebras", "openrouter", "gemini",
    "modelscope", "llm7", "ovhcloud", "sambanova", "cohere",
    "huggingface", "mistral", "cloudflare", "ollama",
]

_FALLBACK_CHAINS: dict[str, list[str]] = {
    pid: [p for p in _ALL_FALLBACKS if p != pid] for pid, _ in [(p.id, p) for p in PROVIDER_CATALOG]
}
_FALLBACK_CHAINS["ollama"] = []  # local is already the last resort; no further fallback
_FALLBACK_CHAINS["custom"] = []  # user-specific arbitrary endpoint; never auto-tried for others


def fallback_chain(provider_id: str) -> list[str]:
    """Ordered list of alternate provider ids to try if `provider_id` fails."""
    return [p for p in _FALLBACK_CHAINS.get(provider_id, []) if p != provider_id]


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
        "modelscope": getattr(settings, "MODELSCOPE_API_KEY", None),
        "cloudflare": getattr(settings, "CLOUDFLARE_API_KEY", None),
        "llm7": getattr(settings, "LLM7_API_KEY", None),
        "ovhcloud": getattr(settings, "OVHCLOUD_API_KEY", None),
        "sambanova": getattr(settings, "SAMBANOVA_API_KEY", None),
        "cohere": getattr(settings, "COHERE_API_KEY", None),
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
        "modelscope": "https://api-inference.modelscope.cn/v1",
        "llm7": "https://api.llm7.io/v1",
        "ovhcloud": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        "sambanova": "https://api.sambanova.ai/v1",
        "cohere": "https://api.cohere.ai/compatibility/v1",
    }

    api_key = override_api_key or env_key_map.get(provider_id)
    base_url = override_base_url or env_base_map.get(provider_id) or meta.default_base_url
    model = override_model or (settings.DEFAULT_MODEL if provider_id == settings.DEFAULT_PROVIDER else meta.default_model)

    if provider_id == "custom":
        # The generic "custom" provider has no defaults at all — it exists
        # purely so users can point Meiko at any OpenAI-compatible endpoint
        # (a self-hosted server, a corporate gateway, or a direct
        # Anthropic-compatible proxy) without us hardcoding that vendor.
        if not base_url:
            raise ValueError(
                "Custom provider requires a base_url (e.g. https://api.your-endpoint.com/v1)."
            )
        if not model:
            raise ValueError("Custom provider requires a model name.")

    # Cloudflare Workers AI bakes the account id into the URL path. Since the
    # Settings UI only has one "API key" field per provider, we accept the
    # key in `account_id:api_token` shorthand and split it here so users
    # don't need a second input box just for this one provider.
    if provider_id == "cloudflare" and api_key and ":" in api_key and "{account_id}" in base_url:
        account_id, _, real_token = api_key.partition(":")
        base_url = base_url.replace("{account_id}", account_id)
        api_key = real_token

    config = ProviderConfig(api_key=api_key, base_url=base_url, model=model)

    if provider_id == "gemini":
        return GeminiProvider(config)
    # All other providers (nvidia, openrouter, groq, openai, ollama, cerebras,
    # huggingface, mistral, modelscope, cloudflare, llm7, ovhcloud, sambanova,
    # cohere) speak an OpenAI-compatible /chat/completions API.
    return OpenAICompatibleProvider(config)
