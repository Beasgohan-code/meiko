import pytest

from app.memory.store import Store

@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    await s.init()
    return s


async def test_conversation_lifecycle(store):
    conv_id = await store.create_conversation("u1", "hello")
    convs = await store.list_conversations("u1")
    assert any(c["id"] == conv_id for c in convs)

    await store.rename_conversation(conv_id, "new title")
    conv = await store.get_conversation(conv_id)
    assert conv["title"] == "new title"

    await store.set_pinned(conv_id, True)
    conv = await store.get_conversation(conv_id)
    assert conv["pinned"] == 1

    await store.delete_conversation(conv_id)
    assert await store.get_conversation(conv_id) is None


async def test_search_conversations_by_title_and_message(store):
    conv_id = await store.create_conversation("u2", "Trip to Kerala")
    await store.add_message(conv_id, "user", "Tell me about backwaters")

    by_title = await store.search_conversations("u2", "Kerala")
    assert any(c["id"] == conv_id for c in by_title)

    by_message = await store.search_conversations("u2", "backwaters")
    assert any(c["id"] == conv_id for c in by_message)

    no_match = await store.search_conversations("u2", "nonexistent_xyz")
    assert no_match == []


async def test_usage_logging_and_summary(store):
    await store.log_usage("u3", "nvidia", "autonomous", tool_calls=2, steps=3, elapsed_seconds=1.5)
    await store.log_usage("u3", "gemini", "chat", tool_calls=0, steps=1, elapsed_seconds=0.2, error=True)

    summary = await store.get_usage_summary("u3", days=30)
    assert summary["totals"]["total"] == 2
    assert summary["totals"]["errors"] == 1
    providers = {row["provider"] for row in summary["by_provider_mode"]}
    assert providers == {"nvidia", "gemini"}


async def test_settings_merge_preserves_other_keys(store):
    await store.set_user_settings("u4", api_keys={"nvidia": "key1"})
    await store.set_user_settings("u4", api_keys={"gemini": "key2"})
    settings = await store.get_user_settings("u4")
    assert settings["api_keys"]["nvidia"] == "key1"
    assert settings["api_keys"]["gemini"] == "key2"
