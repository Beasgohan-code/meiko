"""
Meiko Agent — auth & rate limiting.

- API key auth: if MEIKO_API_KEY is set, clients must send X-API-Key.
  When unset, the API is open (useful for local/dev use).
- Rate limiting: simple in-memory sliding-window limiter keyed by client
  identity (API key if present, else IP). No external dependency (Redis)
  needed for a single-instance deployment; swap in Redis for multi-instance.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from .config import get_settings


async def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    settings = get_settings()
    if not settings.MEIKO_API_KEY:
        return  # auth disabled
    if x_api_key != settings.MEIKO_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


class RateLimiter:
    """Sliding-window limiter: `limit` requests per `window` seconds per key."""

    def __init__(self, limit: int = 60, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        now = time.time()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            retry_after = int(self.window - (now - bucket[0])) + 1
            return False, retry_after
        bucket.append(now)
        return True, 0


_chat_limiter: Optional[RateLimiter] = None
_general_limiter: Optional[RateLimiter] = None


def get_chat_limiter() -> RateLimiter:
    global _chat_limiter
    if _chat_limiter is None:
        settings = get_settings()
        _chat_limiter = RateLimiter(limit=settings.RATE_LIMIT_CHAT_PER_MIN, window=60.0)
    return _chat_limiter


def get_general_limiter() -> RateLimiter:
    global _general_limiter
    if _general_limiter is None:
        settings = get_settings()
        _general_limiter = RateLimiter(limit=settings.RATE_LIMIT_GENERAL_PER_MIN, window=60.0)
    return _general_limiter


def client_identity(request: Request, x_api_key: Optional[str] = None) -> str:
    if x_api_key:
        return f"key:{x_api_key[:8]}"
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


async def enforce_chat_rate_limit(request: Request, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    identity = client_identity(request, x_api_key)
    ok, retry_after = get_chat_limiter().check(identity)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for chat requests. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )


async def enforce_general_rate_limit(request: Request, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    identity = client_identity(request, x_api_key)
    ok, retry_after = get_general_limiter().check(identity)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )
