"""Async client for talking to the Meiko backend's API from the Telegram bot."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from . import config


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.MEIKO_API_KEY:
        headers["X-API-Key"] = config.MEIKO_API_KEY
    return headers


async def stream_chat(
    user_id: str,
    message: str,
    mode: str = "autonomous",
    conversation_id: str | None = None,
    session_id: str | None = None,
    persona_id: str | None = None,
    provider: str | None = None,
) -> AsyncIterator[dict]:
    payload = {
        "user_id": user_id,
        "message": message,
        "mode": mode,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "persona_id": persona_id,
        "provider": provider,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST", f"{config.MEIKO_BACKEND_URL}/api/chat/stream", headers=_headers(), json=payload
        ) as resp:
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if not data:
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue


async def fetch_modes() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/modes")
        return resp.json()


async def fetch_personas() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/personas")
        return resp.json()


async def fetch_providers() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/providers")
        return resp.json()


async def fetch_skills() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/skills")
        return resp.json()


async def fetch_connectors() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/connectors", headers=_headers())
        return resp.json()


async def toggle_connector(connector_id: str, enabled: bool) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{config.MEIKO_BACKEND_URL}/api/connectors/{connector_id}/toggle",
            headers=_headers(),
            json={"enabled": enabled},
        )
        return resp.json()


async def set_user_settings(user_id: str, **kwargs: Any) -> dict:
    payload = {"user_id": user_id, **kwargs}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{config.MEIKO_BACKEND_URL}/api/settings", headers=_headers(), json=payload)
        return resp.json()


async def get_user_settings(user_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/settings", params={"user_id": user_id}, headers=_headers())
        return resp.json()


async def list_conversations(user_id: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/conversations", params={"user_id": user_id}, headers=_headers())
        return resp.json()


async def search_conversations(user_id: str, query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{config.MEIKO_BACKEND_URL}/api/conversations/search",
            params={"user_id": user_id, "q": query},
            headers=_headers(),
        )
        return resp.json()


async def get_conversation_messages(conversation_id: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{config.MEIKO_BACKEND_URL}/api/conversations/{conversation_id}/messages", headers=_headers())
        return resp.json()


async def delete_conversation(conversation_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.delete(f"{config.MEIKO_BACKEND_URL}/api/conversations/{conversation_id}", headers=_headers())
        return resp.json()


async def rename_conversation(conversation_id: str, title: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.patch(
            f"{config.MEIKO_BACKEND_URL}/api/conversations/{conversation_id}", headers=_headers(), json={"title": title}
        )
        return resp.json()


async def get_usage(user_id: str, days: int = 30) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{config.MEIKO_BACKEND_URL}/api/usage", params={"user_id": user_id, "days": days}, headers=_headers()
        )
        return resp.json()


async def upload_file(session_id: str, filename: str, content: bytes, mime: str = "application/octet-stream") -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"file": (filename, content, mime)}
        resp = await client.post(
            f"{config.MEIKO_BACKEND_URL}/api/upload", params={"session_id": session_id}, files=files
        )
        return resp.json()


def download_url(session_id: str, filename: str) -> str:
    return f"{config.MEIKO_BACKEND_URL}/api/download/{session_id}/{filename}"
