
async def test_settings_roundtrip_masks_keys(app_client):
    resp = await app_client.post(
        "/api/settings",
        json={"user_id": "bob", "provider": "gemini", "model": "gemini-2.0-flash", "api_keys": {"gemini": "AIzaSyABCDEFGHIJKLMNOP"}},
    )
    assert resp.status_code == 200

    resp = await app_client.get("/api/settings", params={"user_id": "bob"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "gemini"
    assert "api_keys" not in data  # raw keys must never be returned
    assert "gemini" in data["api_keys_masked"]
    masked = data["api_keys_masked"]["gemini"]
    assert "ABCDEFGHIJKLMNOP" not in masked  # full key body never leaked
    assert masked.startswith("AIza")


async def test_settings_default_for_new_user(app_client):
    resp = await app_client.get("/api/settings", params={"user_id": "brand_new_user"})
    assert resp.status_code == 200
    assert resp.json()["api_keys_masked"] == {}


async def test_settings_custom_base_url_roundtrip(app_client):
    resp = await app_client.post(
        "/api/settings",
        json={
            "user_id": "carol",
            "provider": "custom",
            "model": "my-custom-model",
            "api_keys": {"custom": "sk-fake-secret-key"},
            "custom_base_url": "https://my-endpoint.example.com/v1",
        },
    )
    assert resp.status_code == 200

    resp = await app_client.get("/api/settings", params={"user_id": "carol"})
    data = resp.json()
    assert data["provider"] == "custom"
    assert data["custom_base_url"] == "https://my-endpoint.example.com/v1"
    assert "custom" in data["api_keys_masked"]
