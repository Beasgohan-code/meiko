"""
Sandboxed file read/write/list tools scoped to a per-session workspace
directory, so Meiko can act like a coding/agent harness (create files,
edit them, inspect a small project) without touching the host filesystem.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from .base import Tool


def _workspace_root(session_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.DATA_DIR) / "workspaces" / session_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(session_id: str, rel_path: str) -> Path:
    root = _workspace_root(session_id).resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Path escapes workspace sandbox")
    return target


class WriteFileTool(Tool):
    name = "write_file"
    description = "Create or overwrite a file inside Meiko's sandboxed session workspace. Use for generating code, notes, or documents."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path, e.g. 'app.py'"},
            "content": {"type": "string", "description": "Full file content to write"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, path: str, content: str, **_: Any) -> str:
        session_id = self._session_id_provider()
        target = _safe_path(session_id, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a file from Meiko's sandboxed session workspace."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Relative file path"}},
        "required": ["path"],
    }

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, path: str, **_: Any) -> str:
        session_id = self._session_id_provider()
        target = _safe_path(session_id, path)
        if not target.exists():
            return f"Error: {path} does not exist"
        return target.read_text(encoding="utf-8")[:20000]


class ListFilesTool(Tool):
    name = "list_files"
    description = "List files in Meiko's sandboxed session workspace."
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, **_: Any) -> str:
        session_id = self._session_id_provider()
        root = _workspace_root(session_id)
        files = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
        return "\n".join(files) if files else "(empty workspace)"
