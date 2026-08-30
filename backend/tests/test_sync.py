"""Tests for cross-device sync: pairing codes + live WebSocket push."""
from __future__ import annotations

from starlette.testclient import TestClient


async def test_pairing_code_roundtrip(app_client):
    resp = await app_client.post("/api/sync/pair", json={"user_id": "alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["code"]) == 6
    assert body["expires_in"] == 600

    claim = await app_client.post("/api/sync/claim", json={"code": body["code"]})
    assert claim.status_code == 200
    assert claim.json()["user_id"] == "alice"


async def test_pairing_code_is_single_use(app_client):
    resp = await app_client.post("/api/sync/pair", json={"user_id": "bob"})
    code = resp.json()["code"]

    first = await app_client.post("/api/sync/claim", json={"code": code})
    assert first.status_code == 200

    second = await app_client.post("/api/sync/claim", json={"code": code})
    assert second.status_code == 404


async def test_pairing_code_unknown_is_404(app_client):
    resp = await app_client.post("/api/sync/claim", json={"code": "ZZZZZZ"})
    assert resp.status_code == 404


async def test_pairing_code_is_case_insensitive(app_client):
    resp = await app_client.post("/api/sync/pair", json={"user_id": "carol"})
    code = resp.json()["code"]
    claim = await app_client.post("/api/sync/claim", json={"code": code.lower()})
    assert claim.status_code == 200
    assert claim.json()["user_id"] == "carol"


async def test_sync_status_reports_zero_devices_when_disconnected(app_client):
    resp = await app_client.get("/api/sync/status", params={"user_id": "nobody-connected"})
    assert resp.status_code == 200
    assert resp.json()["connected_devices"] == 0


def test_websocket_receives_settings_update_push(monkeypatch):
    """A second device connected to /ws/sync/{user_id} should be notified the
    moment settings change for that user_id, without polling."""
    import tempfile
    from pathlib import Path

    tmp = tempfile.mkdtemp(prefix="meiko_ws_test_")
    monkeypatch.setenv("DATA_DIR", tmp)
    monkeypatch.setenv("DB_PATH", str(Path(tmp) / "meiko.db"))
    monkeypatch.setenv("MEIKO_API_KEY", "")

    from app.core import config as config_module
    from app.core import sync as sync_module
    from app.memory import store as store_module

    config_module.get_settings.cache_clear()
    store_module._store = None
    sync_module._pairing_registry = None
    sync_module._sync_hub = None

    from app.main import app

    with TestClient(app) as client:  # triggers FastAPI startup (creates DB tables)
        with client.websocket_connect("/ws/sync/device-sync-user") as ws:
            resp = client.post("/api/settings", json={"user_id": "device-sync-user", "provider": "groq"})
            assert resp.status_code == 200
            message = ws.receive_json()
            assert message["event"] == "settings_updated"
