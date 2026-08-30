"""Tests for the optional embeddings helper (memory/embeddings.py)."""
import pytest

from app.memory.embeddings import EmbeddingsClient, cosine_similarity, reciprocal_rank_fusion


def test_cosine_similarity_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_empty_or_mismatched_returns_zero():
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_reciprocal_rank_fusion_prefers_items_ranked_high_in_both():
    keyword = ["a", "b", "c"]
    vector = ["b", "a", "d"]
    fused = reciprocal_rank_fusion(keyword, vector)
    # "a" and "b" both appear near the top of both rankings, so they should
    # outscore "c" and "d" which only appear in one ranking each.
    assert fused["a"] > fused["c"]
    assert fused["b"] > fused["d"]


async def test_embeddings_client_disabled_by_default(monkeypatch):
    from app.core import config as config_module

    config_module.get_settings.cache_clear()
    client = EmbeddingsClient()
    assert client.enabled is False
    assert await client.embed("hello") is None
