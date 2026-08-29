
async def test_health(app_client):
    resp = await app_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_health_ready(app_client):
    resp = await app_client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


async def test_providers_catalog_nonempty(app_client):
    resp = await app_client.get("/api/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 5
    ids = {p["id"] for p in data}
    assert "nvidia" in ids and "gemini" in ids and "ollama" in ids


async def test_modes_catalog(app_client):
    resp = await app_client.get("/api/modes")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()}
    assert {"chat", "research", "code", "autonomous", "creative"} <= ids


async def test_personas_catalog(app_client):
    resp = await app_client.get("/api/personas")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
