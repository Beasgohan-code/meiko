"""
Meiko Agent - SQLite persistence backend (via aiosqlite)

This is the zero-config default store: works out of the box with no setup,
one file on disk. Stores conversations, messages, per-user runtime settings
(provider selection + API keys entered through the Settings UI), and
long-term "memories" (key facts the agent chooses to remember about a user).

Memory search uses SQLite's built-in FTS5 (full-text, BM25-ranked) — no
external vector database needed. If the user configures
`EMBEDDINGS_PROVIDER`, search additionally blends in cosine-similarity
ranking over stored embedding vectors (see memory/embeddings.py) using
reciprocal-rank fusion, giving hybrid keyword+semantic search without a
dedicated vector DB like Chroma.

For multi-worker / higher-concurrency deployments, set `DATABASE_URL` to
switch to the PostgreSQL backend instead (see memory/postgres_store.py) —
`get_store()` in store.py picks whichever backend is configured.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from .embeddings import EmbeddingsClient, cosine_similarity, reciprocal_rank_fusion

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
    custom_base_url TEXT DEFAULT '',
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    embedding TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'github',
    provider_uid TEXT NOT NULL,
    username TEXT NOT NULL,
    name TEXT,
    email TEXT,
    avatar_url TEXT,
    created_at REAL,
    last_login_at REAL,
    UNIQUE(provider, provider_uid)
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    fact, content='memories', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, fact) VALUES (new.rowid, new.fact);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, fact) VALUES ('delete', old.rowid, old.fact);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, fact) VALUES ('delete', old.rowid, old.fact);
    INSERT INTO memories_fts(rowid, fact) VALUES (new.rowid, new.fact);
END;
"""


class SQLiteStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._embeddings = EmbeddingsClient()

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
            ("user_settings", "custom_base_url", "TEXT DEFAULT ''"),
            ("memories", "embedding", "TEXT"),
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
                return {
                    "user_id": user_id, "provider": "nvidia", "model": "", "api_keys": {},
                    "persona": "", "ui_language": "en", "custom_base_url": "",
                }
            d = dict(row)
            d["api_keys"] = json.loads(d.get("api_keys") or "{}")
            d.setdefault("ui_language", "en")
            d.setdefault("custom_base_url", "")
            return d

    async def set_user_settings(
        self,
        user_id: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_keys: Optional[dict[str, str]] = None,
        persona: Optional[str] = None,
        ui_language: Optional[str] = None,
        custom_base_url: Optional[str] = None,
    ) -> None:
        current = await self.get_user_settings(user_id)
        merged_keys = current["api_keys"]
        if api_keys:
            merged_keys.update(api_keys)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_settings (user_id, provider, model, api_keys, persona, ui_language, custom_base_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    provider = excluded.provider,
                    model = excluded.model,
                    api_keys = excluded.api_keys,
                    persona = excluded.persona,
                    ui_language = excluded.ui_language,
                    custom_base_url = excluded.custom_base_url,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    provider or current["provider"],
                    model if model is not None else current["model"],
                    json.dumps(merged_keys),
                    persona if persona is not None else current["persona"],
                    ui_language if ui_language is not None else current.get("ui_language", "en"),
                    custom_base_url if custom_base_url is not None else current.get("custom_base_url", ""),
                    time.time(),
                ),
            )
            await db.commit()

    # ---------- Long-term memories ----------
    async def add_memory(self, user_id: str, fact: str) -> str:
        mem_id = str(uuid.uuid4())
        embedding = await self._embeddings.embed(fact)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO memories (id, user_id, fact, embedding, created_at) VALUES (?, ?, ?, ?, ?)",
                (mem_id, user_id, fact, json.dumps(embedding) if embedding else None, time.time()),
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
                "SELECT id, user_id, fact, created_at FROM memories WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_memory(self, memory_id: str) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT id, user_id, fact, created_at FROM memories WHERE id = ?", (memory_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def delete_memory(self, memory_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await db.commit()

    async def clear_memories(self, user_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
            await db.commit()

    async def search_memories(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Hybrid memory search: SQLite FTS5 (BM25 keyword ranking) always
        runs; if EMBEDDINGS_PROVIDER is configured, cosine-similarity ranking
        over stored embedding vectors is fused in via reciprocal-rank fusion.
        Falls back gracefully to pure keyword search (or even a plain
        substring scan) with zero configuration — no vector DB required."""
        query = query.strip()
        if not query:
            return (await self.list_memories_full(user_id, limit))

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # FTS5 query syntax breaks on bare punctuation; keep it forgiving.
            fts_query = " OR ".join(f'"{w}"' for w in query.split() if w) or query
            keyword_rows: list[dict[str, Any]] = []
            try:
                cur = await db.execute(
                    """
                    SELECT m.id, m.user_id, m.fact, m.embedding, m.created_at, bm25(memories_fts) AS rank
                    FROM memories_fts
                    JOIN memories m ON m.rowid = memories_fts.rowid
                    WHERE memories_fts MATCH ? AND m.user_id = ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, user_id, max(limit * 3, 30)),
                )
                keyword_rows = [dict(r) for r in await cur.fetchall()]
            except Exception:
                # Malformed FTS query (rare, e.g. pure stopwords/symbols) — fall
                # back to a plain LIKE scan so search never hard-fails.
                like = f"%{query}%"
                cur = await db.execute(
                    "SELECT id, user_id, fact, embedding, created_at FROM memories WHERE user_id = ? AND fact LIKE ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, like, limit),
                )
                keyword_rows = [dict(r) for r in await cur.fetchall()]

            by_id = {r["id"]: r for r in keyword_rows}
            keyword_ranked_ids = [r["id"] for r in keyword_rows]

            if not self._embeddings.enabled:
                return [
                    {k: v for k, v in r.items() if k != "embedding"} for r in keyword_rows[:limit]
                ]

            query_vec = await self._embeddings.embed(query)
            if not query_vec:
                return [
                    {k: v for k, v in r.items() if k != "embedding"} for r in keyword_rows[:limit]
                ]

            # Score every embedded memory for this user against the query
            # vector (a personal memory store is small — hundreds to low
            # thousands of rows — so a full scan is plenty fast and needs no
            # separate ANN index / vector database).
            cur = await db.execute(
                "SELECT id, user_id, fact, embedding, created_at FROM memories WHERE user_id = ? AND embedding IS NOT NULL",
                (user_id,),
            )
            all_embedded = [dict(r) for r in await cur.fetchall()]
            for r in all_embedded:
                by_id.setdefault(r["id"], r)
            scored = [
                (r["id"], cosine_similarity(query_vec, json.loads(r["embedding"])))
                for r in all_embedded
            ]
            scored.sort(key=lambda t: t[1], reverse=True)
            vector_ranked_ids = [i for i, _ in scored[: max(limit * 3, 30)]]

            fused = reciprocal_rank_fusion(keyword_ranked_ids, vector_ranked_ids)
            ordered_ids = sorted(fused.keys(), key=lambda i: fused[i], reverse=True)[:limit]
            return [
                {k: v for k, v in by_id[i].items() if k != "embedding"}
                for i in ordered_ids
                if i in by_id
            ]

    # ---------- User accounts (GitHub OAuth) ----------
    async def get_or_create_oauth_user(
        self,
        provider: str,
        provider_uid: str,
        username: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Look up a user by (provider, provider_uid), creating one on first
        login. The Meiko-internal `id` is what becomes the account's stable
        `user_id` used everywhere else in the app (conversations, settings,
        memories) — so once someone logs in, their data follows their
        GitHub identity across every device instead of a made-up string."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM users WHERE provider = ? AND provider_uid = ?", (provider, provider_uid)
            )
            row = await cur.fetchone()
            if row:
                user_id = row["id"]
                await db.execute(
                    "UPDATE users SET username=?, name=?, email=?, avatar_url=?, last_login_at=? WHERE id=?",
                    (username, name, email, avatar_url, now, user_id),
                )
                await db.commit()
                return {
                    "id": user_id,
                    "provider": provider,
                    "provider_uid": provider_uid,
                    "username": username,
                    "name": name,
                    "email": email,
                    "avatar_url": avatar_url,
                }
            user_id = f"gh_{provider_uid}"
            await db.execute(
                """INSERT INTO users (id, provider, provider_uid, username, name, email, avatar_url, created_at, last_login_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, provider, provider_uid, username, name, email, avatar_url, now, now),
            )
            await db.commit()
            return {
                "id": user_id,
                "provider": provider,
                "provider_uid": provider_uid,
                "username": username,
                "name": name,
                "email": email,
                "avatar_url": avatar_url,
            }

    async def get_user(self, user_id: str) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None



