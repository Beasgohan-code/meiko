async def test_models_endpoint_default_nvidia(app_client):
    resp = await app_client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 5
    assert any(m["id"] == "mistralai/mistral-nemotron" for m in data)
    assert all("display_name" in m for m in data)


async def test_models_endpoint_per_provider(app_client):
    providers = [
        "nvidia", "gemini", "groq", "openrouter", "openai", "ollama", "cerebras", "huggingface", "mistral",
        "modelscope", "cloudflare", "llm7", "ovhcloud", "sambanova", "cohere",
    ]
    for provider in providers:
        resp = await app_client.get("/api/models", params={"provider": provider})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


async def test_models_endpoint_unknown_provider_empty(app_client):
    resp = await app_client.get("/api/models", params={"provider": "does-not-exist"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_memories_lifecycle(app_client):
    from app.memory.store import get_store

    store = get_store()
    await store.add_memory("mem_user", "Likes concise answers")
    mem_id = (await store.list_memories_full("mem_user"))[0]["id"]

    resp = await app_client.get("/api/memories", params={"user_id": "mem_user"})
    assert resp.status_code == 200
    assert any(m["fact"] == "Likes concise answers" for m in resp.json())

    resp = await app_client.delete(f"/api/memories/{mem_id}")
    assert resp.status_code == 200
    resp = await app_client.get("/api/memories", params={"user_id": "mem_user"})
    assert not any(m["id"] == mem_id for m in resp.json())


async def test_add_memory_endpoint(app_client):
    resp = await app_client.post("/api/memories", json={"user_id": "add_mem_user", "fact": "Prefers dark mode"})
    assert resp.status_code == 200
    assert "id" in resp.json()

    resp = await app_client.get("/api/memories", params={"user_id": "add_mem_user"})
    assert any(m["fact"] == "Prefers dark mode" for m in resp.json())


async def test_skill_detail_endpoint_404_for_missing(app_client):
    resp = await app_client.get("/api/skills/does-not-exist")
    assert resp.status_code == 404


async def test_memories_search_endpoint(app_client):
    from app.memory.store import get_store

    store = get_store()
    await store.add_memory("search_user", "Favorite language is Python")
    await store.add_memory("search_user", "Lives in Kerala")

    resp = await app_client.get("/api/memories", params={"user_id": "search_user", "q": "Python"})
    assert resp.status_code == 200
    facts = [m["fact"] for m in resp.json()]
    assert any("Python" in f for f in facts)


async def test_settings_ui_language_roundtrip(app_client):
    resp = await app_client.post("/api/settings", json={"user_id": "lang_user", "ui_language": "es"})
    assert resp.status_code == 200
    resp = await app_client.get("/api/settings", params={"user_id": "lang_user"})
    assert resp.status_code == 200
    assert resp.json()["ui_language"] == "es"
