"""
Meiko Agent - Tool Interface

Every tool exposes an OpenAI-style function schema (for the LLM tool-calling
API) plus an async `run(**kwargs)` implementation. The ToolRegistry collects
all built-in tools and exposes them to the harness.
"""
from __future__ import annotations

import abc
from typing import Any


class Tool(abc.ABC):
    name: str = "base_tool"
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abc.abstractmethod
    async def run(self, **kwargs: Any) -> str:
        """Execute the tool and return a string result (or JSON string)."""
        raise NotImplementedError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self, enabled: set[str] | None = None) -> list[dict[str, Any]]:
        tools = self.all() if enabled is None else [t for t in self.all() if t.name in enabled]
        return [t.schema() for t in tools]
