"""Shared pytest fixtures for the Meiko backend test suite."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch):
    """Give every test its own throwaway DATA_DIR so tests never touch real data
    or leak state into each other via the SQLite file."""
    tmp = tempfile.mkdtemp(prefix="meiko_test_")
    monkeypatch.setenv("DATA_DIR", tmp)
    monkeypatch.setenv("DB_PATH", str(Path(tmp) / "meiko.db"))
    monkeypatch.setenv("MEIKO_API_KEY", "")
    # Reset cached settings/store singletons between tests.
    from app.core import config as config_module
    from app.core import sync as sync_module
    from app.memory import store as store_module

    config_module.get_settings.cache_clear()
    store_module._store = None  # type: ignore[attr-defined]
    sync_module._pairing_registry = None  # type: ignore[attr-defined]
    sync_module._sync_hub = None  # type: ignore[attr-defined]
    yield tmp


@pytest.fixture
async def app_client():
    """An httpx AsyncClient wired directly to the FastAPI app (no network)."""
    import httpx

    from app.main import app
    from app.memory.store import get_store

    await get_store().init()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
