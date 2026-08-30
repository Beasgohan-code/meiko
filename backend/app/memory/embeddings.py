"""
Optional embeddings client for semantic/hybrid memory search.

Meiko's memory search works out of the box with zero configuration using
plain keyword search (SQLite FTS5 / Postgres tsvector — see store.py and
postgres_store.py). If the user configures `EMBEDDINGS_PROVIDER` (any
provider that exposes an OpenAI-compatible `/embeddings` endpoint — NVIDIA
NIM, OpenAI, Mistral, Cohere, etc. all do, many for free), Meiko additionally
computes a vector for every remembered fact and blends vector similarity
into search ranking (reciprocal-rank fusion of keyword rank + cosine
similarity), similar in spirit to hermus-agent-free's `mem2 hybrid` command
— without needing a dedicated vector database like Chroma.

This intentionally has zero hard dependencies (no numpy/torch): cosine
similarity is a few lines of pure Python, which is plenty fast for a
personal agent's memory store (hundreds to low thousands of facts).
"""
from __future__ import annotations

import math
from typing import Optional

import httpx

from ..core.config import Settings, get_settings


def _provider_embeddings_endpoint(provider_id: str, settings: Settings) -> tuple[Optional[str], Optional[str]]:
    """Return (base_url, api_key) for a provider's OpenAI-compatible
    /embeddings endpoint, reusing the same env vars as chat providers."""
    from ..providers.registry import build_provider

    try:
        provider = build_provider(provider_id, settings)
    except Exception:  # noqa: BLE001
        return None, None
    base_url = getattr(provider, "base_url", None) or getattr(provider.config, "base_url", None)
    api_key = provider.config.api_key
    return base_url, api_key


class EmbeddingsClient:
    """Thin wrapper that computes an embedding vector for a piece of text,
    or returns None if embeddings are not configured / the call fails.
    Failures are always non-fatal — memory keeps working via keyword search."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.provider_id = (getattr(self.settings, "EMBEDDINGS_PROVIDER", "") or "").strip().lower()
        self.model = getattr(self.settings, "EMBEDDINGS_MODEL", "") or "nvidia/nv-embedqa-e5-v5"

    @property
    def enabled(self) -> bool:
        return bool(self.provider_id)

    async def embed(self, text: str) -> Optional[list[float]]:
        if not self.enabled or not text.strip():
            return None
        base_url, api_key = _provider_embeddings_endpoint(self.provider_id, self.settings)
        if not base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.post(
                    f"{base_url.rstrip('/')}/embeddings",
                    headers=headers,
                    json={"model": self.model, "input": text[:8000]},
                )
                if resp.status_code >= 400:
                    return None
                data = resp.json()
                vec = data["data"][0]["embedding"]
                return [float(x) for x in vec]
        except Exception:  # noqa: BLE001
            return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def reciprocal_rank_fusion(
    keyword_ranked_ids: list[str],
    vector_ranked_ids: list[str],
    k: int = 60,
) -> dict[str, float]:
    """Classic RRF: combined_score(id) = sum(1 / (k + rank)) across each
    ranking the id appears in. Simple, parameter-light, and works well when
    combining two very differently-scaled rankers (BM25/ts_rank vs cosine)."""
    scores: dict[str, float] = {}
    for rank, _id in enumerate(keyword_ranked_ids):
        scores[_id] = scores.get(_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, _id in enumerate(vector_ranked_ids):
        scores[_id] = scores.get(_id, 0.0) + 1.0 / (k + rank + 1)
    return scores
