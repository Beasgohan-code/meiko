"""
Web search tool. Uses free DuckDuckGo search (via ddgs) by default,
falling back to Tavily if a TAVILY_API_KEY is configured.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from ..core.config import get_settings
from .base import Tool


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the live web for up-to-date information (news, facts, docs). "
        "Returns a JSON list of {title, url, snippet}. Use this when the user asks "
        "about recent events, or anything you are not confident about from memory."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
            "max_results": {"type": "integer", "description": "Number of results (default 5)", "default": 5},
        },
        "required": ["query"],
    }

    async def run(self, query: str, max_results: int = 5, **_: Any) -> str:
        settings = get_settings()
        if settings.TAVILY_API_KEY:
            return await self._tavily_search(query, max_results, settings.TAVILY_API_KEY)
        return await self._ddg_search(query, max_results)

    async def _ddg_search(self, query: str, max_results: int) -> str:
        def _sync_search() -> list[dict[str, str]]:
            try:
                from ddgs import DDGS

                with DDGS() as ddgs:
                    results = []
                    for r in ddgs.text(query, max_results=max_results):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                        })
                    return results
            except Exception as e:  # pragma: no cover
                return [{"error": str(e)}]

        results = await asyncio.to_thread(_sync_search)
        return json.dumps(results, ensure_ascii=False)

    async def _tavily_search(self, query: str, max_results: int, api_key: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": max_results},
            )
            data = resp.json()
            results = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
                for r in data.get("results", [])
            ]
            return json.dumps(results, ensure_ascii=False)
