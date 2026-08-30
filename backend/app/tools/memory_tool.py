"""Long-term memory tools so Meiko can remember facts about a user across sessions."""
from __future__ import annotations

from typing import Any

from ..memory.store import get_store
from .base import Tool


class RememberTool(Tool):
    name = "remember"
    description = "Save an important fact about the user or task for long-term memory, to recall in future conversations (e.g. preferences, name, ongoing project details)."
    parameters = {
        "type": "object",
        "properties": {"fact": {"type": "string", "description": "The fact to remember, written concisely"}},
        "required": ["fact"],
    }

    def __init__(self, user_id_provider):
        self._user_id_provider = user_id_provider

    async def run(self, fact: str, **_: Any) -> str:
        store = get_store()
        await store.add_memory(self._user_id_provider(), fact)
        return f"Remembered: {fact}"


class RecallTool(Tool):
    name = "recall_memories"
    description = (
        "Retrieve previously remembered facts about this user. Pass `query` to "
        "search memories by relevance (hybrid keyword + semantic search) instead "
        "of just listing the most recent ones — use this when you need a specific "
        "fact rather than a general refresh."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional search query to find the most relevant memories instead of the most recent ones.",
            }
        },
        "required": [],
    }

    def __init__(self, user_id_provider):
        self._user_id_provider = user_id_provider

    async def run(self, query: str = "", **_: Any) -> str:
        store = get_store()
        user_id = self._user_id_provider()
        if query.strip():
            results = await store.search_memories(user_id, query)
            facts = [r["fact"] for r in results]
        else:
            facts = await store.list_memories(user_id)
        return "\n".join(f"- {m}" for m in facts) if facts else "No memories stored yet."
