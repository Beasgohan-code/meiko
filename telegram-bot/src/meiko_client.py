"""Async client for talking to the Meiko backend's streaming chat API from the Telegram bot."""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from . import config


async def stream_chat(
    user_id: str,
    message: str,
    mode: str = "autonomous",
    conversation_id: str | None = None,
    session_id: str | None = None,
    persona_id: str | None = None,
) -> AsyncIterator[dict]:
    headers = {"Content-Type": "application/json"}
    if config.MEIKO_API_KEY:
        headers["X-API-Key"] = config.MEIKO_API_KEY

    payload = {
        "user_id": user_id,
        "message": message,
        "mode": mode,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "persona_id": persona_id,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST", f"{config.MEIKO_BACKEND_URL}/api/chat/stream", headers=headers, json=payload
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


async def set_user_settings(user_id: str, **kwargs) -> dict:
    headers = {"Content-Type": "application/json"}
    if config.MEIKO_API_KEY:
        headers["X-API-Key"] = config.MEIKO_API_KEY
    payload = {"user_id": user_id, **kwargs}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{config.MEIKO_BACKEND_URL}/api/settings", headers=headers, json=payload)
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
