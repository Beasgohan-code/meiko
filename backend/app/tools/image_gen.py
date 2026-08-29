"""
Image generation tool.

Uses the free, keyless Pollinations.ai open image API by default (no
account needed — great "works out of the box" default), but will use
NVIDIA NIM's image endpoints or Gemini image generation if the user has
configured those keys and requests them explicitly via config.
"""
from __future__ import annotations

import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from ..core.config import get_settings
from .base import Tool


def _workspace_root(session_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.DATA_DIR) / "workspaces" / session_id / "images"
    root.mkdir(parents=True, exist_ok=True)
    return root


class GenerateImageTool(Tool):
    name = "generate_image"
    description = (
        "Generate an image from a text prompt and save it into the session workspace. "
        "Returns the relative file path (e.g. images/xyz.png) which can be shown to the user. "
        "Free, no API key required by default."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Description of the image to generate"},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
        },
        "required": ["prompt"],
    }

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, prompt: str, width: int = 1024, height: int = 1024, **_: Any) -> str:
        session_id = self._session_id_provider()
        root = _workspace_root(session_id)
        filename = f"img_{int(time.time() * 1000)}.png"
        out_path = root / filename

        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        params = {"width": width, "height": height, "nologo": "true"}

        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
        except Exception as e:  # noqa: BLE001
            return f"Error generating image: {e}"

        return f"images/{filename}"
