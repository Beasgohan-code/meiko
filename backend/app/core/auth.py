"""
Meiko Agent — user accounts & GitHub OAuth.

Meiko has always worked "accountless": every client makes up a `user_id`
string and the backend just partitions data by whatever string it's given
(see core/sync.py's pairing codes, which exist purely to let two devices
agree on the same string). That still works and stays fully supported for
local/self-hosted use with zero setup.

This module adds a *real* opt-in account system on top of it:

- `GET  /api/auth/config`          -> tells the client whether GitHub login
                                       is configured on this server (so the
                                       UI can hide the button if not).
- `GET  /api/auth/github/login`    -> redirects the browser to GitHub's
                                       OAuth authorize screen.
- `GET  /api/auth/github/callback` -> GitHub redirects back here with a
                                       `code`; we exchange it for a GitHub
                                       access token, fetch the profile, and
                                       get-or-create a Meiko `User` row keyed
                                       by the stable GitHub numeric id. We
                                       then mint a signed JWT session token
                                       and redirect the browser back to the
                                       web app with it in the URL fragment
                                       (never sent to a server as a query
                                       param, so it can't leak into access
                                       logs), where the frontend stores it
                                       and calls `/api/auth/me` to confirm.
- `GET  /api/auth/me`              -> resolves the bearer JWT to a user.
- `POST /api/auth/logout`          -> stateless (JWT-based), included for a
                                       symmetric client experience / future
                                       token-revocation hook.

Once logged in, a user's stable Meiko `user_id` becomes their GitHub-derived
account id instead of a client-generated string, so conversations/settings/
memories naturally follow them across devices without needing the old
pairing-code dance (which still works too, for anonymous use).

No new external dependency beyond PyJWT + the httpx already in use.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Optional

import httpx
import jwt
from fastapi import Header, HTTPException, status

from .config import get_settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API = "https://api.github.com/user"
GITHUB_EMAILS_API = "https://api.github.com/user/emails"

JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _jwt_secret() -> str:
    settings = get_settings()
    # Falls back to SECRET_KEY so a fresh install "just works" for local
    # dev; operators should set a real SECRET_KEY (or JWT_SECRET) in prod.
    return settings.JWT_SECRET or settings.SECRET_KEY


def github_oauth_configured() -> bool:
    settings = get_settings()
    return bool(settings.GITHUB_OAUTH_CLIENT_ID and settings.GITHUB_OAUTH_CLIENT_SECRET)


def build_github_authorize_url(redirect_uri: str, state: str) -> str:
    settings = get_settings()
    params = (
        f"client_id={settings.GITHUB_OAUTH_CLIENT_ID}"
        f"&redirect_uri={httpx.QueryParams({'x': redirect_uri})['x']}"
        f"&scope=read:user user:email"
        f"&state={state}"
        f"&allow_signup=true"
    )
    return f"{GITHUB_AUTHORIZE_URL}?{params}"


async def exchange_github_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an OAuth `code` for an access token, then fetch the GitHub
    profile (and a verified primary email if the scope allows it). Raises
    HTTPException on any failure so the callback route can surface a clean
    error instead of a stack trace."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
                "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        token_data = token_resp.json() if token_resp.status_code < 400 else {}
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail=f"GitHub OAuth exchange failed: {token_data}")

        gh_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
        user_resp = await client.get(GITHUB_USER_API, headers=gh_headers)
        if user_resp.status_code >= 400:
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub profile")
        profile = user_resp.json()

        email = profile.get("email")
        if not email:
            try:
                emails_resp = await client.get(GITHUB_EMAILS_API, headers=gh_headers)
                if emails_resp.status_code < 400:
                    emails = emails_resp.json()
                    primary = next((e for e in emails if e.get("primary")), None)
                    email = (primary or (emails[0] if emails else {})).get("email")
            except Exception:  # noqa: BLE001
                pass

    return {
        "github_id": str(profile.get("id")),
        "username": profile.get("login") or f"github-{profile.get('id')}",
        "avatar_url": profile.get("avatar_url"),
        "email": email,
        "name": profile.get("name"),
    }


def issue_session_token(user_id: str, username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Session expired, please sign in again") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid session token") from exc


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict[str, Any]]:
    """FastAPI dependency: resolves a Bearer JWT if present, else None.
    Routes that work fine anonymously (the vast majority of Meiko's API)
    use this so logged-in *and* accountless clients both work unchanged."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        return decode_session_token(token)
    except HTTPException:
        return None


async def require_user(
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """FastAPI dependency for routes that require a real logged-in account
    (e.g. dev-mode saved agent profiles synced server-side)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    token = authorization.split(" ", 1)[1].strip()
    return decode_session_token(token)
