"""Tests for the optional GitHub-OAuth account system (app/core/auth.py).

These exercise the pieces that don't require a live GitHub round-trip:
- /api/auth/config correctly reports enabled/disabled
- login/callback are gated off when OAuth isn't configured
- JWT issue/decode roundtrip
- get_or_create_oauth_user creates once and updates on repeat login
- /api/auth/me resolves a valid session token to the right user
"""
from __future__ import annotations


async def test_auth_config_disabled_by_default(app_client):
    resp = await app_client.get("/api/auth/config")
    assert resp.status_code == 200
    assert resp.json() == {"github_enabled": False}


async def test_github_login_503_when_not_configured(app_client):
    resp = await app_client.get("/api/auth/github/login", follow_redirects=False)
    assert resp.status_code == 503


async def test_github_callback_503_when_not_configured(app_client):
    resp = await app_client.get(
        "/api/auth/github/callback", params={"code": "x", "state": "y"}, follow_redirects=False
    )
    assert resp.status_code == 503


async def test_auth_me_requires_bearer_token(app_client):
    resp = await app_client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_auth_me_rejects_garbage_token(app_client):
    resp = await app_client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


async def test_jwt_issue_and_decode_roundtrip(monkeypatch):
    from app.core import auth as auth_core
    from app.core.config import get_settings

    get_settings.cache_clear()
    token = auth_core.issue_session_token("gh_123", "octocat")
    payload = auth_core.decode_session_token(token)
    assert payload["sub"] == "gh_123"
    assert payload["username"] == "octocat"


async def test_get_or_create_oauth_user_then_auth_me(app_client, monkeypatch):
    from app.core import auth as auth_core
    from app.memory.store import get_store

    store = get_store()
    await store.init()
    user = await store.get_or_create_oauth_user(
        provider="github",
        provider_uid="999",
        username="octocat",
        name="The Octocat",
        email="octo@example.com",
        avatar_url="https://example.com/a.png",
    )
    assert user["id"] == "gh_999"

    # logging in again with the same provider_uid must update, not duplicate
    user2 = await store.get_or_create_oauth_user(
        provider="github", provider_uid="999", username="octocat-renamed"
    )
    assert user2["id"] == user["id"]
    fetched = await store.get_user(user["id"])
    assert fetched["username"] == "octocat-renamed"

    token = auth_core.issue_session_token(user["id"], "octocat-renamed")
    resp = await app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "gh_999"
    assert data["username"] == "octocat-renamed"


async def test_auth_me_404_for_unknown_user(app_client):
    from app.core import auth as auth_core

    token = auth_core.issue_session_token("gh_does_not_exist", "ghost")
    resp = await app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_github_login_rejects_disallowed_client_redirect(app_client, monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "abc")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "def")
    from app.core.config import get_settings

    get_settings.cache_clear()
    resp = await app_client.get(
        "/api/auth/github/login",
        params={"client_redirect": "https://evil.example.com/steal"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    get_settings.cache_clear()


async def test_github_login_allows_meiko_scheme_redirect(app_client, monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "abc")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "def")
    from app.core.config import get_settings

    get_settings.cache_clear()
    resp = await app_client.get(
        "/api/auth/github/login",
        params={"client_redirect": "meiko://auth"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    assert "github.com/login/oauth/authorize" in resp.headers["location"]
    get_settings.cache_clear()


async def test_auth_config_enabled_when_env_set(app_client, monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "abc")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "def")
    from app.core.config import get_settings

    get_settings.cache_clear()
    resp = await app_client.get("/api/auth/config")
    assert resp.json() == {"github_enabled": True}
    get_settings.cache_clear()
