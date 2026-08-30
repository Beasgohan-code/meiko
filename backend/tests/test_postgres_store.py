"""
Tests for the PostgreSQL persistence backend (app/memory/postgres_store.py).

These run against a real Postgres instance so hybrid search (native
full-text search via tsvector/GIN) and the async connection pool are
exercised for real, not mocked. Set `MEIKO_TEST_DATABASE_URL` to a
Postgres DSN to run them (CI provides a `postgres:17` service container —
see .github/workflows/backend-ci.yml). Skipped automatically if the
Postgres server isn't reachable, so local runs without Postgres installed
still pass the rest of the suite.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.asyncio

DATABASE_URL = os.environ.get("MEIKO_TEST_DATABASE_URL", "")


async def _make_store():
    from app.memory.postgres_store import PostgresStore

    store = PostgresStore(DATABASE_URL)
    await store.init()
    return store


@pytest.fixture
async def store():
    if not DATABASE_URL:
        pytest.skip("MEIKO_TEST_DATABASE_URL not set — skipping PostgreSQL backend tests")
    s = await _make_store()
    yield s
    # Clean up all rows this test run touched instead of dropping tables, so
    # concurrent test runs against a shared DB (e.g. local dev) don't collide.
    await s.close()


def _uid() -> str:
    return f"pgtest-{uuid.uuid4().hex[:8]}"


async def test_conversation_lifecycle(store):
    user = _uid()
    conv_id = await store.create_conversation(user, "hello")
    convs = await store.list_conversations(user)
    assert any(c["id"] == conv_id for c in convs)

    await store.rename_conversation(conv_id, "new title")
    conv = await store.get_conversation(conv_id)
    assert conv["title"] == "new title"

    await store.set_pinned(conv_id, True)
    conv = await store.get_conversation(conv_id)
    assert conv["pinned"] == 1

    await store.delete_conversation(conv_id)
    assert await store.get_conversation(conv_id) is None


async def test_messages_and_search(store):
    user = _uid()
    conv_id = await store.create_conversation(user, "Trip to Kerala")
    await store.add_message(conv_id, "user", "Tell me about backwaters")

    messages = await store.get_messages(conv_id)
    assert len(messages) == 1
    assert messages[0]["content"] == "Tell me about backwaters"

    by_title = await store.search_conversations(user, "Kerala")
    assert any(c["id"] == conv_id for c in by_title)

    by_message = await store.search_conversations(user, "backwaters")
    assert any(c["id"] == conv_id for c in by_message)


async def test_usage_logging_and_summary(store):
    user = _uid()
    await store.log_usage(user, "nvidia", "autonomous", tool_calls=2, steps=3, elapsed_seconds=1.5)
    await store.log_usage(user, "gemini", "chat", tool_calls=0, steps=1, elapsed_seconds=0.2, error=True)

    summary = await store.get_usage_summary(user, days=30)
    assert summary["totals"]["total"] == 2
    assert summary["totals"]["errors"] == 1
    providers = {row["provider"] for row in summary["by_provider_mode"]}
    assert providers == {"nvidia", "gemini"}


async def test_settings_merge_preserves_other_keys(store):
    user = _uid()
    await store.set_user_settings(user, api_keys={"nvidia": "key1"})
    await store.set_user_settings(user, api_keys={"gemini": "key2"})
    settings = await store.get_user_settings(user)
    assert settings["api_keys"]["nvidia"] == "key1"
    assert settings["api_keys"]["gemini"] == "key2"


async def test_memory_lifecycle_and_fulltext_search(store):
    user = _uid()
    await store.add_memory(user, "User's favorite programming language is Python")
    await store.add_memory(user, "User lives in Kerala, India")
    await store.add_memory(user, "User is building an AI agent called Meiko")

    facts = await store.list_memories(user)
    assert len(facts) == 3

    results = await store.search_memories(user, "Meiko agent")
    assert any("Meiko" in r["fact"] for r in results)

    mem_id = (await store.list_memories_full(user))[0]["id"]
    fetched = await store.get_memory(mem_id)
    assert fetched["id"] == mem_id

    await store.delete_memory(mem_id)
    assert await store.get_memory(mem_id) is None

    await store.clear_memories(user)
    assert await store.list_memories(user) == []


async def test_memory_search_scoped_to_user(store):
    alice, bob = _uid(), _uid()
    await store.add_memory(alice, "Alice loves hiking in the mountains")
    await store.add_memory(bob, "Bob loves hiking too")

    results = await store.search_memories(alice, "hiking")
    assert all(r["user_id"] == alice for r in results)


async def test_memory_search_empty_query_returns_recent(store):
    user = _uid()
    id1 = await store.add_memory(user, "first fact")
    id2 = await store.add_memory(user, "second fact")

    results = await store.search_memories(user, "")
    ids = {r["id"] for r in results}
    assert {id1, id2} <= ids
