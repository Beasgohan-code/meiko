"""Tests for the SQLite-backed hybrid memory search (FTS5 keyword ranking,
with optional embeddings blended in via reciprocal-rank fusion)."""
import pytest

from app.memory.sqlite_store import SQLiteStore


@pytest.fixture
async def store(tmp_path):
    s = SQLiteStore(str(tmp_path / "test.db"))
    await s.init()
    return s


async def test_search_memories_keyword_ranking(store):
    await store.add_memory("u1", "User's favorite programming language is Python")
    await store.add_memory("u1", "User lives in Kerala, India")
    await store.add_memory("u1", "User is building an AI agent called Meiko")
    await store.add_memory("u1", "User's dog is named Max")

    results = await store.search_memories("u1", "Meiko agent")
    assert results, "expected at least one match"
    assert any("Meiko" in r["fact"] for r in results)


async def test_search_memories_scoped_to_user(store):
    await store.add_memory("alice", "Alice loves hiking")
    await store.add_memory("bob", "Bob loves hiking too")

    results = await store.search_memories("alice", "hiking")
    assert all(r["user_id"] == "alice" for r in results)
    assert any("Alice" in r["fact"] for r in results)


async def test_search_memories_empty_query_returns_recent(store):
    id1 = await store.add_memory("u2", "first fact")
    id2 = await store.add_memory("u2", "second fact")

    results = await store.search_memories("u2", "")
    ids = {r["id"] for r in results}
    assert {id1, id2} <= ids


async def test_search_memories_no_match_returns_empty(store):
    await store.add_memory("u3", "The sky is blue")
    results = await store.search_memories("u3", "xyzabc_nonexistent_term")
    assert results == []


async def test_search_memories_survives_delete(store):
    mem_id = await store.add_memory("u4", "Deletable fact about kayaking")
    await store.delete_memory(mem_id)
    results = await store.search_memories("u4", "kayaking")
    assert results == []


async def test_search_memories_handles_symbol_only_query_gracefully(store):
    await store.add_memory("u5", "Some fact")
    # Pure punctuation would otherwise raise a malformed FTS5 MATCH error —
    # search_memories must fall back gracefully instead of raising.
    results = await store.search_memories("u5", "***")
    assert isinstance(results, list)
