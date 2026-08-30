"""
Meiko Agent — cross-device sync primitives.

Every client (web, native Android, Flutter, Telegram, CLI) already talks to
the same backend keyed by `user_id`, so conversations/settings/memory are
*stored* centrally. What was missing is a way for a human to (a) make two
different installs share the same `user_id` without typing a long UUID by
hand, and (b) find out *live* that something changed on another device
instead of only seeing it after a manual refresh. This module provides both:

- Pairing codes: device A calls `create_pairing_code(user_id)` to get a
  short, human-typeable 6-character code good for 10 minutes. Device B calls
  `claim_pairing_code(code)` to resolve it back to device A's `user_id` and
  then simply starts using that id for every request — no accounts, no
  passwords, just "type this code into your other device".
- A tiny in-memory WebSocket pub/sub keyed by `user_id`. Any mutation
  (new message, settings change, memory add/delete, conversation
  rename/delete/pin) calls `publish(user_id, event)`, and every other
  connected client for that same `user_id` gets a small JSON nudge over
  `/ws/sync/{user_id}` telling it what changed so it can refetch just that
  slice of state instead of polling.

This intentionally mirrors the in-memory `RateLimiter` design already used
in `core/security.py` — no Redis/external dependency needed for a
single-process deployment; both could be swapped for a shared backend later
if Meiko is ever run with multiple worker processes.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import string
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import WebSocket

_PAIRING_CODE_ALPHABET = string.ascii_uppercase + string.digits
_PAIRING_CODE_TTL_SECONDS = 10 * 60  # 10 minutes


@dataclass
class _PairingEntry:
    user_id: str
    expires_at: float


class PairingRegistry:
    """Short-lived, single-use codes that resolve to a `user_id`."""

    def __init__(self) -> None:
        self._codes: dict[str, _PairingEntry] = {}

    def _sweep(self) -> None:
        now = time.time()
        expired = [c for c, e in self._codes.items() if e.expires_at < now]
        for c in expired:
            self._codes.pop(c, None)

    def create(self, user_id: str) -> dict[str, Any]:
        self._sweep()
        code = "".join(secrets.choice(_PAIRING_CODE_ALPHABET) for _ in range(6))
        expires_at = time.time() + _PAIRING_CODE_TTL_SECONDS
        self._codes[code] = _PairingEntry(user_id=user_id, expires_at=expires_at)
        return {"code": code, "expires_in": _PAIRING_CODE_TTL_SECONDS}

    def claim(self, code: str) -> Optional[str]:
        self._sweep()
        entry = self._codes.pop(code.strip().upper(), None)
        if not entry:
            return None
        return entry.user_id


@dataclass
class SyncHub:
    """Per-`user_id` WebSocket fan-out for lightweight change notifications."""

    _connections: dict[str, set[WebSocket]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            peers = self._connections.get(user_id)
            if peers is not None:
                peers.discard(ws)
                if not peers:
                    self._connections.pop(user_id, None)

    async def publish(self, user_id: str, event: str, data: Optional[dict[str, Any]] = None) -> None:
        peers = self._connections.get(user_id)
        if not peers:
            return
        payload = json.dumps({"event": event, "data": data or {}, "ts": time.time()})
        dead: list[WebSocket] = []
        for ws in list(peers):
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    peers.discard(ws)

    def device_count(self, user_id: str) -> int:
        return len(self._connections.get(user_id, ()))


_pairing_registry: Optional[PairingRegistry] = None
_sync_hub: Optional[SyncHub] = None


def get_pairing_registry() -> PairingRegistry:
    global _pairing_registry
    if _pairing_registry is None:
        _pairing_registry = PairingRegistry()
    return _pairing_registry


def get_sync_hub() -> SyncHub:
    global _sync_hub
    if _sync_hub is None:
        _sync_hub = SyncHub()
    return _sync_hub
