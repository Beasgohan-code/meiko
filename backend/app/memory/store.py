"""
Meiko Agent — Persistence layer dispatcher.

Meiko ships with a zero-config SQLite backend (see sqlite_store.py) that
needs no setup at all. Setting `DATABASE_URL` in the environment switches
the *entire* persistence layer — conversations, messages, settings,
memories, and memory search — to PostgreSQL instead (see
postgres_store.py), for deployments that want a real multi-writer database
server rather than a single SQLite file.

Both backends implement the exact same async interface (create_conversation,
list_messages, add_memory, search_memories, ...) so nothing else in the app
needs to know or care which one is active — `get_store()` is the only thing
that decides.

`Store` is kept as an alias for `SQLiteStore` for backward compatibility
(existing tests construct `Store(path)` directly to get an isolated SQLite
instance regardless of which backend is configured for the live app).
"""
from __future__ import annotations

from typing import Optional, Union

from ..core.config import get_settings
from .postgres_store import PostgresStore
from .sqlite_store import SQLiteStore

# Backward-compatible alias: tests and any external code that did
# `from app.memory.store import Store` keep working unchanged.
Store = SQLiteStore

AnyStore = Union[SQLiteStore, PostgresStore]

_store: Optional[AnyStore] = None


def get_store() -> AnyStore:
    global _store
    if _store is None:
        settings = get_settings()
        if getattr(settings, "DATABASE_URL", None):
            _store = PostgresStore(settings.DATABASE_URL)
        else:
            _store = SQLiteStore(settings.DB_PATH)
    return _store
