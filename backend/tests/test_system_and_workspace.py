"""
Tests for the Phase 6 web-app-parity endpoints inspired by OmniRoute's
Health Dashboard (GET /api/system/status) and Open Design's artifact tree
(GET /api/workspace/{session_id}/files) — plus the enriched `final` agent
event that now carries which provider/model actually answered, so the web
app can render a per-answer run-telemetry badge.
"""
from __future__ import annotations

from pathlib import Path


async def test_system_status_ok(app_client):
    resp = await app_client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["store"]["backend"] == "sqlite"
    assert data["store"]["reachable"] is True
    assert data["providers"]["total"] > 10
    assert data["providers"]["keyless"] >= 1  # ollama is keyless
    assert data["connectors"]["total"] > 5
    assert data["connectors"]["tool_count"] >= data["connectors"]["total"]
    assert isinstance(data["skills"], int)
    assert data["uptime_seconds"] >= 0
    assert data["version"]


async def test_workspace_files_empty_when_no_session(app_client):
    resp = await app_client.get("/api/workspace/does-not-exist-session/files")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_workspace_files_lists_generated_files(app_client):
    # main.py binds `settings = get_settings()` once at import time, so the
    # route handler's Path(settings.DATA_DIR) is that original bound object
    # regardless of any later monkeypatch/cache_clear — read from there.
    from app import main as main_module

    data_dir = Path(main_module.settings.DATA_DIR)
    session_id = "artifact-test-session"
    ws = data_dir / "workspaces" / session_id
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "report.md").write_text("# Report\n", encoding="utf-8")
    (ws / "images").mkdir()
    (ws / "images" / "chart.png").write_bytes(b"\x89PNG\r\n")

    exports = data_dir / "exports" / session_id
    exports.mkdir(parents=True, exist_ok=True)
    (exports / "bundle.zip").write_bytes(b"PK\x03\x04")


    resp = await app_client.get(f"/api/workspace/{session_id}/files")
    assert resp.status_code == 200
    files = resp.json()
    names = {f["name"] for f in files}
    assert "report.md" in names
    assert str(Path("images") / "chart.png") in names
    assert "bundle.zip" in names
    kinds = {f["name"]: f["kind"] for f in files}
    assert kinds["report.md"] == "workspace"
    assert kinds["bundle.zip"] == "exports"
    for f in files:
        assert f["size_bytes"] > 0
        assert f["download_url"].startswith(f"/api/download/{session_id}/")


async def test_workspace_files_path_traversal_is_contained(app_client):
    # FastAPI's own path routing already rejects a `/`-containing segment in
    # a single {session_id} path param (it doesn't match this route at all),
    # so `..` traversal via the session_id can't reach outside DATA_DIR.
    resp = await app_client.get("/api/workspace/..%2F..%2Fetc/files")
    assert resp.status_code == 404

    # A same-segment ".." session_id is taken literally as a directory name
    # (Path(session_id).name === "..") and safely resolves to nothing found,
    # never escaping DATA_DIR.
    resp = await app_client.get("/api/workspace/..%2e/files")
    assert resp.status_code == 200
    assert resp.json() == []
