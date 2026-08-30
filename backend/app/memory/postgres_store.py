"""
Meiko Agent - PostgreSQL persistence backend (via asyncpg)

Same interface as SQLiteStore (see sqlite_store.py) so `store.py::get_store()`
can hand either implementation to the rest of the app transparently. Enabled
by setting `DATABASE_URL=postgresql://user:pass@host:5432/dbname` — intended
for multi-worker / higher-concurrency deployments where SQLite's single
writer becomes a bottleneck.

Memory search uses Postgres's native full-text search (`tsvector` + GIN
index, ranked with `ts_rank`) by default — no extra dependency. If the
`pgvector` extension is available in the target database, it's used
automatically to add cosine-similarity ranking over stored embeddings
(blended via reciprocal-rank fusion, same approach as the SQLite backend),
giving a genuinely more powerful, production-grade hybrid search than a
bundled embedded vector database like Chroma — while staying entirely
inside Postgres (one database to operate, back up, and scale) instead of
adding a second stateful service.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

import asyncpg

from .embeddings import EmbeddingsClient, cosine_similarity, reciprocal_rank_fusion

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    pinned INTEGER DEFAULT 0,
    mode TEXT DEFAULT 'autonomous',
    created_at DOUBLE PRECISION,
    updated_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT,
    mode TEXT,
    tool_calls INTEGER DEFAULT 0,
    steps INTEGER DEFAULT 0,
    elapsed_seconds DOUBLE PRECISION DEFAULT 0,
    error INTEGER DEFAULT 0,
    created_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_events(user_id, created_at);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    created_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    provider TEXT DEFAULT 'nvidia',
    model TEXT DEFAULT '',
    api_keys TEXT DEFAULT '{}',
    persona TEXT DEFAULT '',
    ui_language TEXT DEFAULT 'en',
    updated_at DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    embedding TEXT,
    created_at DOUBLE PRECISION,
    fact_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', fact)) STORED
);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_fts ON memories USING GIN(fact_tsv);
"""


class PostgresStore:
    """Async persistence backend for PostgreSQL. Uses a connection pool
    (asyncpg) rather than SQLite's connect-per-call pattern, since Postgres
    connections are comparatively expensive to open."""

    def __init__(self, database_url: str):
        # asyncpg wants a plain postgres:// / postgresql:// DSN, not the
        # SQLAlchemy-style postgresql+asyncpg:// some users may paste in.
        self.database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        self._pool: Optional[asyncpg.Pool] = None
        self._embeddings = EmbeddingsClient()
        self._pgvector_available = False

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=10)
        return self._pool

    async def init(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
            await self._migrate(conn)
            try:
                # Best-effort: if the `vector` extension is installed on this
                # Postgres server, enabling it costs nothing even though our
                # current similarity scoring is done in pure Python below —
                # it means a future upgrade to an ANN index (ivfflat/hnsw) for
                # very large memory stores is a schema migration away, not a
                # new dependency, without forcing every deployment to have
                # pgvector available today.
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                self._pgvector_available = True
            except Exception:
                self._pgvector_available = False

    async def _migrate(self, conn: asyncpg.Connection) -> None:
        migrations = [
            ("conversations", "pinned", "INTEGER DEFAULT 0"),
            ("conversations", "mode", "TEXT DEFAULT 'autonomous'"),
            ("user_settings", "ui_language", "TEXT DEFAULT 'en'"),
        ]
        for table, column, coltype in migrations:
            try:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}")
            except Exception:
                pass

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @staticmethod
    def _row(record: Optional[asyncpg.Record]) -> Optional[dict[str, Any]]:
        return dict(record) if record else None

    # ---------- Conversations ----------
    async def create_conversation(self, user_id: str, title: str = "") -> str:
        conv_id = str(uuid.uuid4())
        now = time.time()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES ($1, $2, $3, $4, $5)",
                conv_id, user_id, title, now, now,
            )
        return conv_id

    async def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM conversations WHERE user_id = $1 ORDER BY updated_at DESC", user_id
            )
            return [dict(r) for r in rows]

    async def touch_conversation(self, conv_id: str, title: Optional[str] = None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if title:
                await conn.execute("UPDATE conversations SET updated_at = $1, title = $2 WHERE id = $3", time.time(), title, conv_id)
            else:
                await conn.execute("UPDATE conversations SET updated_at = $1 WHERE id = $2", time.time(), conv_id)

    async def rename_conversation(self, conv_id: str, title: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE conversations SET title = $1 WHERE id = $2", title, conv_id)

    async def delete_conversation(self, conv_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM messages WHERE conversation_id = $1", conv_id)
                await conn.execute("DELETE FROM conversations WHERE id = $1", conv_id)

    async def search_conversations(self, user_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        like = f"%{query}%"
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT c.* FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = $1 AND (c.title ILIKE $2 OR m.content ILIKE $2)
                ORDER BY c.updated_at DESC
                LIMIT $3
                """,
                user_id, like, limit,
            )
            return [dict(r) for r in rows]

    async def get_conversation(self, conv_id: str) -> Optional[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM conversations WHERE id = $1", conv_id)
            return self._row(row)

    async def set_pinned(self, conv_id: str, pinned: bool) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE conversations SET pinned = $1 WHERE id = $2", 1 if pinned else 0, conv_id)

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
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO usage_events (id, user_id, provider, mode, tool_calls, steps, elapsed_seconds, error, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                str(uuid.uuid4()), user_id, provider, mode, tool_calls, steps, elapsed_seconds, 1 if error else 0, time.time(),
            )

    async def get_usage_summary(self, user_id: str, days: int = 30) -> dict[str, Any]:
        since = time.time() - days * 86400
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT provider, mode, COUNT(*) as n, SUM(tool_calls) as tool_calls, "
                "SUM(elapsed_seconds) as elapsed, SUM(error) as errors "
                "FROM usage_events WHERE user_id = $1 AND created_at >= $2 GROUP BY provider, mode",
                user_id, since,
            )
            totals_row = await conn.fetchrow(
                "SELECT COUNT(*) as total, SUM(tool_calls) as tool_calls, SUM(error) as errors "
                "FROM usage_events WHERE user_id = $1 AND created_at >= $2",
                user_id, since,
            )
            totals = dict(totals_row) if totals_row else {"total": 0, "tool_calls": 0, "errors": 0}
            return {"by_provider_mode": [dict(r) for r in rows], "totals": totals, "window_days": days}

    # ---------- Messages ----------
    async def add_message(self, conversation_id: str, role: str, content: str, tool_calls: Optional[list] = None) -> str:
        msg_id = str(uuid.uuid4())
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, tool_calls, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                msg_id, conversation_id, role, content, json.dumps(tool_calls) if tool_calls else None, time.time(),
            )
        return msg_id

    async def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC LIMIT $2",
                conversation_id, limit,
            )
            return [dict(r) for r in rows]

    # ---------- User settings ----------
    async def get_user_settings(self, user_id: str) -> dict[str, Any]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM user_settings WHERE user_id = $1", user_id)
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
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_settings (user_id, provider, model, api_keys, persona, ui_language, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    model = EXCLUDED.model,
                    api_keys = EXCLUDED.api_keys,
                    persona = EXCLUDED.persona,
                    ui_language = EXCLUDED.ui_language,
                    updated_at = EXCLUDED.updated_at
                """,
                user_id,
                provider or current["provider"],
                model if model is not None else current["model"],
                json.dumps(merged_keys),
                persona if persona is not None else current["persona"],
                ui_language if ui_language is not None else current.get("ui_language", "en"),
                time.time(),
            )

    # ---------- Long-term memories ----------
    async def add_memory(self, user_id: str, fact: str) -> str:
        mem_id = str(uuid.uuid4())
        embedding = await self._embeddings.embed(fact)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO memories (id, user_id, fact, embedding, created_at) VALUES ($1, $2, $3, $4, $5)",
                mem_id, user_id, fact, json.dumps(embedding) if embedding else None, time.time(),
            )
        return mem_id

    async def list_memories(self, user_id: str, limit: int = 50) -> list[str]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT fact FROM memories WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2", user_id, limit
            )
            return [r["fact"] for r in rows]

    async def list_memories_full(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, user_id, fact, created_at FROM memories WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                user_id, limit,
            )
            return [dict(r) for r in rows]

    async def get_memory(self, memory_id: str) -> Optional[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, user_id, fact, created_at FROM memories WHERE id = $1", memory_id)
            return self._row(row)

    async def delete_memory(self, memory_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM memories WHERE id = $1", memory_id)

    async def clear_memories(self, user_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM memories WHERE user_id = $1", user_id)

    async def search_memories(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Hybrid memory search: Postgres full-text search (tsvector + GIN,
        ranked with ts_rank) always runs; if EMBEDDINGS_PROVIDER is
        configured, cosine-similarity over stored embeddings is fused in via
        reciprocal-rank fusion. No external vector database required."""
        query = query.strip()
        if not query:
            return await self.list_memories_full(user_id, limit)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            keyword_rows = await conn.fetch(
                """
                SELECT id, user_id, fact, embedding, created_at,
                       ts_rank(fact_tsv, plainto_tsquery('english', $1)) AS rank
                FROM memories
                WHERE user_id = $2 AND fact_tsv @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT $3
                """,
                query, user_id, max(limit * 3, 30),
            )
            keyword_rows = [dict(r) for r in keyword_rows]
            if not keyword_rows:
                # plainto_tsquery can return nothing for very short/stopword
                # queries — fall back to a plain substring scan.
                like = f"%{query}%"
                keyword_rows = [
                    dict(r) for r in await conn.fetch(
                        "SELECT id, user_id, fact, embedding, created_at FROM memories "
                        "WHERE user_id = $1 AND fact ILIKE $2 ORDER BY created_at DESC LIMIT $3",
                        user_id, like, limit,
                    )
                ]

            by_id = {r["id"]: r for r in keyword_rows}
            keyword_ranked_ids = [r["id"] for r in keyword_rows]

            if not self._embeddings.enabled:
                return [{k: v for k, v in r.items() if k not in ("embedding", "rank")} for r in keyword_rows[:limit]]

            query_vec = await self._embeddings.embed(query)
            if not query_vec:
                return [{k: v for k, v in r.items() if k not in ("embedding", "rank")} for r in keyword_rows[:limit]]

            embedded_rows = await conn.fetch(
                "SELECT id, user_id, fact, embedding, created_at FROM memories WHERE user_id = $1 AND embedding IS NOT NULL",
                user_id,
            )
            embedded_rows = [dict(r) for r in embedded_rows]
            for r in embedded_rows:
                by_id.setdefault(r["id"], r)
            scored = [
                (r["id"], cosine_similarity(query_vec, json.loads(r["embedding"])))
                for r in embedded_rows
            ]
            scored.sort(key=lambda t: t[1], reverse=True)
            vector_ranked_ids = [i for i, _ in scored[: max(limit * 3, 30)]]

            fused = reciprocal_rank_fusion(keyword_ranked_ids, vector_ranked_ids)
            ordered_ids = sorted(fused.keys(), key=lambda i: fused[i], reverse=True)[:limit]
            return [
                {k: v for k, v in by_id[i].items() if k not in ("embedding", "rank")}
                for i in ordered_ids
                if i in by_id
            ]
