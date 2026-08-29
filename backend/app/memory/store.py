"""
Meiko Agent - Persistence layer (SQLite via aiosqlite)

Stores: conversations, messages, per-user runtime settings (provider
selection + API keys entered through the Settings UI), and long-term
"memories" (key facts the agent chooses to remember about a user).
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from ..core.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    pinned INTEGER DEFAULT 0,
    mode TEXT DEFAULT 'autonomous',
    created_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT,
    mode TEXT,
    tool_calls INTEGER DEFAULT 0,
    steps INTEGER DEFAULT 0,
    elapsed_seconds REAL DEFAULT 0,
    error INTEGER DEFAULT 0,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    created_at REAL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    provider TEXT DEFAULT 'nvidia',
    model TEXT DEFAULT '',
    api_keys TEXT DEFAULT '{}',
    persona TEXT DEFAULT '',
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    created_at REAL
);
"""


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
            await self._migrate(db)

    async def _migrate(self, db: aiosqlite.Connection) -> None:
        """Best-effort additive migrations for columns introduced after v1."""
        migrations = [
            ("conversations", "pinned", "INTEGER DEFAULT 0"),
            ("conversations", "mode", "TEXT DEFAULT 'autonomous'"),
            ("user_settings", "ui_language", "TEXT DEFAULT 'en'"),
        ]
        for table, column, coltype in migrations:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                await db.commit()
            except Exception:
                pass  # column already exists

    # ---------- Conversations ----------
    async def create_conversation(self, user_id: str, title: str = "") -> str:
        conv_id = str(uuid.uuid4())
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conv_id, user_id, title, now, now),
            )
            await db.commit()
        return conv_id

    async def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def touch_conversation(self, conv_id: str, title: Optional[str] = None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            if title:
                await db.execute("UPDATE conversations SET updated_at = ?, title = ? WHERE id = ?", (time.time(), title, conv_id))
            else:
                await db.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (time.time(), conv_id))
            await db.commit()

    async def rename_conversation(self, conv_id: str, title: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
            await db.commit()

    async def delete_conversation(self, conv_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            await db.commit()

    async def search_conversations(self, user_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search conversations by title, or by message content within them."""
        like = f"%{query}%"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT DISTINCT c.* FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = ? AND (c.title LIKE ? OR m.content LIKE ?)
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (user_id, like, like, limit),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_conversation(self, conv_id: str) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def set_pinned(self, conv_id: str, pinned: bool) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE conversations SET pinned = ? WHERE id = ?", (1 if pinned else 0, conv_id))
            await db.commit()

    async def log_usage(
        self,
        user_id: str,
        provider: str,
        mode: str,
        tool_calls: int = 0,
        steps: int = 0,
        elapsed_seconds: float = 0.0,
        error: bool = False,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO usage_events (id, user_id, provider, mode, tool_calls, steps, elapsed_seconds, error, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, provider, mode, tool_calls, steps, elapsed_seconds, 1 if error else 0, time.time()),
            )
            await db.commit()

    async def get_usage_summary(self, user_id: str, days: int = 30) -> dict[str, Any]:
        since = time.time() - days * 86400
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT provider, mode, COUNT(*) as n, SUM(tool_calls) as tool_calls, "
                "SUM(elapsed_seconds) as elapsed, SUM(error) as errors "
                "FROM usage_events WHERE user_id = ? AND created_at >= ? GROUP BY provider, mode",
                (user_id, since),
            )
            rows = [dict(r) for r in await cur.fetchall()]
            cur2 = await db.execute(
                "SELECT COUNT(*) as total, SUM(tool_calls) as tool_calls, SUM(error) as errors "
                "FROM usage_events WHERE user_id = ? AND created_at >= ?",
                (user_id, since),
            )
            totals = dict(await cur2.fetchone())
            return {"by_provider_mode": rows, "totals": totals, "window_days": days}

    # ---------- Messages ----------
    async def add_message(self, conversation_id: str, role: str, content: str, tool_calls: Optional[list] = None) -> str:
        msg_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, tool_calls, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, conversation_id, role, content, json.dumps(tool_calls) if tool_calls else None, time.time()),
            )
            await db.commit()
        return msg_id

    async def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
                (conversation_id, limit),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # ---------- User settings (provider + API keys from Settings UI) ----------
    async def get_user_settings(self, user_id: str) -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            if not row:
                return {"user_id": user_id, "provider": "nvidia", "model": "", "api_keys": {}, "persona": "", "ui_language": "en"}
            d = dict(row)
            d["api_keys"] = json.loads(d.get("api_keys") or "{}")
            d.setdefault("ui_language", "en")
            return d

    async def set_user_settings(
        self,
        user_id: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_keys: Optional[dict[str, str]] = None,
        persona: Optional[str] = None,
        ui_language: Optional[str] = None,
    ) -> None:
        current = await self.get_user_settings(user_id)
        merged_keys = current["api_keys"]
        if api_keys:
            merged_keys.update(api_keys)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_settings (user_id, provider, model, api_keys, persona, ui_language, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    provider = excluded.provider,
                    model = excluded.model,
                    api_keys = excluded.api_keys,
                    persona = excluded.persona,
                    ui_language = excluded.ui_language,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    provider or current["provider"],
                    model if model is not None else current["model"],
                    json.dumps(merged_keys),
                    persona if persona is not None else current["persona"],
                    ui_language if ui_language is not None else current.get("ui_language", "en"),
                    time.time(),
                ),
            )
            await db.commit()

    # ---------- Long-term memories ----------
    async def add_memory(self, user_id: str, fact: str) -> str:
        mem_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO memories (id, user_id, fact, created_at) VALUES (?, ?, ?, ?)",
                (mem_id, user_id, fact, time.time()),
            )
            await db.commit()
        return mem_id

    async def list_memories(self, user_id: str, limit: int = 50) -> list[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT fact FROM memories WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
            )
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def list_memories_full(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM memories WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def delete_memory(self, memory_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await db.commit()

    async def clear_memories(self, user_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
            await db.commit()



_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        settings = get_settings()
        _store = Store(settings.DB_PATH)
    return _store
