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
    description = "Retrieve previously remembered facts about this user."
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, user_id_provider):
        self._user_id_provider = user_id_provider

    async def run(self, **_: Any) -> str:
        store = get_store()
        memories = await store.list_memories(self._user_id_provider())
        return "\n".join(f"- {m}" for m in memories) if memories else "No memories stored yet."
