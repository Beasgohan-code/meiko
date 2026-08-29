"""Fetch and extract readable text content from a URL (used to 'read' pages found via web_search)."""
from __future__ import annotations

from typing import Any

import httpx

from .base import Tool


class FetchUrlTool(Tool):
    name = "fetch_url"
    description = "Fetch a web page by URL and return its readable text content (article extraction). Use after web_search to read a promising result in full."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The full URL to fetch"},
        },
        "required": ["url"],
    }

    async def run(self, url: str, **_: Any) -> str:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (MeikoAgent)"}) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            return f"Error fetching {url}: {e}"

        try:
            import trafilatura

            extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
            if extracted:
                return extracted[:8000]
        except Exception:
            pass

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = " ".join(soup.get_text(separator=" ").split())
            return text[:8000]
        except Exception as e:
            return f"Error parsing {url}: {e}"
