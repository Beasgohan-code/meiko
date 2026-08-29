"""
Curated model catalogs per provider — powers the "choose your model" pickers
in the web app, mobile app, native Kotlin app, and Telegram bot.

NVIDIA NIM (build.nvidia.com) hosts 100+ free models; we curate the most
useful chat/agentic ones with friendly names + capability badges so users can
pick intelligently (e.g. "needs long context" -> DeepSeek V4 Pro / Nemotron
Super, "needs vision" -> Llama 3.2 Vision / MiniMax M3, "fastest" -> Nemotron
Nano). Other providers get a smaller, similarly-curated list.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelMeta:
    id: str
    display_name: str
    family: str = ""
    reasoning: bool = False
    vision: bool = False
    context_window: str = ""
    good_for: list[str] = field(default_factory=list)
    tag: str = ""  # e.g. "flagship", "fast", "coding"


NVIDIA_MODELS: list[ModelMeta] = [
    ModelMeta(
        id="mistralai/mistral-nemotron",
        display_name="Mistral Nemotron",
        family="Mistral",
        context_window="128K",
        good_for=["general chat", "balanced default"],
        tag="default",
    ),
    ModelMeta(
        id="deepseek-ai/deepseek-v4-pro",
        display_name="DeepSeek V4 Pro",
        family="DeepSeek",
        reasoning=True,
        context_window="1M",
        good_for=["coding", "long documents", "deep reasoning"],
        tag="flagship",
    ),
    ModelMeta(
        id="deepseek-ai/deepseek-v4-flash",
        display_name="DeepSeek V4 Flash",
        family="DeepSeek",
        reasoning=True,
        context_window="1M",
        good_for=["fast coding", "agentic tool use"],
        tag="fast",
    ),
    ModelMeta(
        id="deepseek-ai/deepseek-v3.2",
        display_name="DeepSeek V3.2",
        family="DeepSeek",
        reasoning=True,
        context_window="128K",
        good_for=["reasoning", "math"],
    ),
    ModelMeta(
        id="moonshotai/kimi-k2.6",
        display_name="Kimi K2.6",
        family="Moonshot",
        reasoning=True,
        context_window="256K",
        good_for=["agentic workflows", "long context chat"],
        tag="flagship",
    ),
    ModelMeta(
        id="moonshotai/kimi-k2-thinking",
        display_name="Kimi K2 Thinking",
        family="Moonshot",
        reasoning=True,
        context_window="128K",
        good_for=["step-by-step reasoning"],
    ),
    ModelMeta(
        id="z-ai/glm-5.2",
        display_name="GLM 5.2",
        family="Z.ai",
        reasoning=True,
        context_window="128K",
        good_for=["long-horizon agentic tasks"],
        tag="flagship",
    ),
    ModelMeta(
        id="z-ai/glm4.7",
        display_name="GLM 4.7",
        family="Z.ai",
        reasoning=True,
        context_window="128K",
        good_for=["general reasoning"],
    ),
    ModelMeta(
        id="qwen/qwen3-235b-a22b",
        display_name="Qwen3 235B",
        family="Qwen",
        reasoning=True,
        context_window="128K",
        good_for=["multilingual chat", "reasoning"],
    ),
    ModelMeta(
        id="qwen/qwen3-coder-480b-a35b-instruct",
        display_name="Qwen3 Coder 480B",
        family="Qwen",
        reasoning=True,
        context_window="256K",
        good_for=["coding", "large codebases"],
        tag="coding",
    ),
    ModelMeta(
        id="meta/llama-4-maverick-17b-128e-instruct",
        display_name="Llama 4 Maverick",
        family="Meta",
        context_window="1M",
        good_for=["general chat", "huge context"],
    ),
    ModelMeta(
        id="meta/llama-3.1-405b-instruct",
        display_name="Llama 3.1 405B",
        family="Meta",
        context_window="128K",
        good_for=["general chat", "high quality"],
    ),
    ModelMeta(
        id="meta/llama-3.2-90b-vision-instruct",
        display_name="Llama 3.2 90B Vision",
        family="Meta",
        vision=True,
        context_window="128K",
        good_for=["image understanding", "vision Q&A"],
        tag="vision",
    ),
    ModelMeta(
        id="minimaxai/minimax-m3",
        display_name="MiniMax M3",
        family="MiniMax",
        reasoning=True,
        vision=True,
        context_window="1M",
        good_for=["multimodal reasoning", "coding"],
        tag="vision",
    ),
    ModelMeta(
        id="mistralai/mistral-large-3-675b-instruct-2512",
        display_name="Mistral Large 3",
        family="Mistral",
        context_window="128K",
        good_for=["general chat", "European languages"],
    ),
    ModelMeta(
        id="mistralai/devstral-2-123b-instruct-2512",
        display_name="Devstral 2 123B",
        family="Mistral",
        context_window="128K",
        good_for=["coding agents"],
        tag="coding",
    ),
    ModelMeta(
        id="nvidia/nemotron-3-super-120b-a12b",
        display_name="Nemotron 3 Super 120B",
        family="NVIDIA",
        reasoning=True,
        context_window="1M",
        good_for=["long context", "reasoning"],
    ),
    ModelMeta(
        id="nvidia/nemotron-3-nano-30b-a3b",
        display_name="Nemotron 3 Nano 30B",
        family="NVIDIA",
        context_window="128K",
        good_for=["fastest replies", "low latency"],
        tag="fast",
    ),
    ModelMeta(
        id="nvidia/llama-3.3-nemotron-super-49b-v1.5",
        display_name="Nemotron Super 49B",
        family="NVIDIA",
        reasoning=True,
        context_window="128K",
        good_for=["balanced reasoning + speed"],
    ),
    ModelMeta(
        id="openai/gpt-oss-120b",
        display_name="GPT-OSS 120B",
        family="OpenAI (open weight)",
        context_window="128K",
        good_for=["general chat"],
    ),
    ModelMeta(
        id="microsoft/phi-4-mini-flash-reasoning",
        display_name="Phi-4 Mini Flash Reasoning",
        family="Microsoft",
        reasoning=True,
        context_window="128K",
        good_for=["fast lightweight reasoning"],
        tag="fast",
    ),
    ModelMeta(
        id="ibm/granite-3.3-8b-instruct",
        display_name="Granite 3.3 8B",
        family="IBM",
        context_window="128K",
        good_for=["lightweight, efficient chat"],
        tag="fast",
    ),
]

GEMINI_MODELS: list[ModelMeta] = [
    ModelMeta(id="gemini-2.0-flash", display_name="Gemini 2.0 Flash", vision=True, context_window="1M", good_for=["fast multimodal chat"], tag="default"),
    ModelMeta(id="gemini-1.5-flash", display_name="Gemini 1.5 Flash", vision=True, context_window="1M", good_for=["fast multimodal chat"]),
    ModelMeta(id="gemini-1.5-pro", display_name="Gemini 1.5 Pro", vision=True, reasoning=True, context_window="2M", good_for=["complex reasoning", "long documents"], tag="flagship"),
]

GROQ_MODELS: list[ModelMeta] = [
    ModelMeta(id="llama-3.3-70b-versatile", display_name="Llama 3.3 70B", context_window="128K", good_for=["general chat"], tag="default"),
    ModelMeta(id="llama-3.1-8b-instant", display_name="Llama 3.1 8B Instant", context_window="128K", good_for=["ultra-fast replies"], tag="fast"),
    ModelMeta(id="deepseek-r1-distill-llama-70b", display_name="DeepSeek R1 Distill 70B", reasoning=True, context_window="128K", good_for=["reasoning"]),
    ModelMeta(id="mixtral-8x7b-32768", display_name="Mixtral 8x7B", context_window="32K", good_for=["general chat"]),
]

OPENROUTER_MODELS: list[ModelMeta] = [
    ModelMeta(id="meta-llama/llama-3.1-8b-instruct:free", display_name="Llama 3.1 8B (free)", context_window="128K", good_for=["general chat"], tag="default"),
    ModelMeta(id="deepseek/deepseek-chat:free", display_name="DeepSeek Chat (free)", reasoning=True, context_window="64K", good_for=["reasoning"]),
    ModelMeta(id="google/gemma-2-9b-it:free", display_name="Gemma 2 9B (free)", context_window="8K", good_for=["lightweight chat"]),
    ModelMeta(id="qwen/qwen-2.5-7b-instruct:free", display_name="Qwen 2.5 7B (free)", context_window="32K", good_for=["multilingual chat"]),
]

OPENAI_MODELS: list[ModelMeta] = [
    ModelMeta(id="gpt-4o-mini", display_name="GPT-4o mini", vision=True, context_window="128K", good_for=["general chat"], tag="default"),
    ModelMeta(id="gpt-4o", display_name="GPT-4o", vision=True, reasoning=True, context_window="128K", good_for=["flagship reasoning"], tag="flagship"),
]

OLLAMA_MODELS: list[ModelMeta] = [
    ModelMeta(id="llama3.1", display_name="Llama 3.1 (local)", context_window="128K", good_for=["fully offline chat"], tag="default"),
    ModelMeta(id="qwen2.5", display_name="Qwen 2.5 (local)", context_window="32K", good_for=["fully offline chat"]),
    ModelMeta(id="deepseek-r1", display_name="DeepSeek R1 (local)", reasoning=True, context_window="32K", good_for=["local reasoning"]),
]

CEREBRAS_MODELS: list[ModelMeta] = [
    ModelMeta(id="llama-3.3-70b", display_name="Llama 3.3 70B (Cerebras)", context_window="128K", good_for=["extremely fast replies"], tag="fast"),
]

HUGGINGFACE_MODELS: list[ModelMeta] = [
    ModelMeta(id="meta-llama/Llama-3.3-70B-Instruct", display_name="Llama 3.3 70B", context_window="128K", good_for=["general chat"], tag="default"),
]

MISTRAL_MODELS: list[ModelMeta] = [
    ModelMeta(id="mistral-small-latest", display_name="Mistral Small", context_window="32K", good_for=["general chat"], tag="default"),
    ModelMeta(id="mistral-large-latest", display_name="Mistral Large", reasoning=True, context_window="128K", good_for=["complex reasoning"], tag="flagship"),
]

MODEL_CATALOG: dict[str, list[ModelMeta]] = {
    "nvidia": NVIDIA_MODELS,
    "gemini": GEMINI_MODELS,
    "groq": GROQ_MODELS,
    "openrouter": OPENROUTER_MODELS,
    "openai": OPENAI_MODELS,
    "ollama": OLLAMA_MODELS,
    "cerebras": CEREBRAS_MODELS,
    "huggingface": HUGGINGFACE_MODELS,
    "mistral": MISTRAL_MODELS,
}


def list_models(provider_id: str) -> list[ModelMeta]:
    return MODEL_CATALOG.get(provider_id, [])
