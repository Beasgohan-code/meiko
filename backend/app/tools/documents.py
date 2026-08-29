"""
Document/export tools — auto-generate .py / .md files from content, and
package the whole session workspace into a downloadable .zip. This is what
gives Meiko its "auto py/md/zip" capability requested for the harness.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from .base import Tool


def _workspace_root(session_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.DATA_DIR) / "workspaces" / session_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _exports_root(session_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.DATA_DIR) / "exports" / session_id
    root.mkdir(parents=True, exist_ok=True)
    return root


class MakeDocumentTool(Tool):
    name = "make_document"
    description = (
        "Create a document file (.md markdown or .py python source) from given content and save it into "
        "the session workspace. Use this to hand the user a clean downloadable file instead of a long chat reply."
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "File name, e.g. 'report.md' or 'script.py'"},
            "content": {"type": "string", "description": "Full content of the document"},
        },
        "required": ["filename", "content"],
    }

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, filename: str, content: str, **_: Any) -> str:
        session_id = self._session_id_provider()
        root = _workspace_root(session_id)
        if not (filename.endswith(".md") or filename.endswith(".py") or filename.endswith(".txt") or filename.endswith(".json")):
            filename += ".md"
        target = root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Saved document to {filename} ({len(content)} bytes). It's available in the workspace file list."


class MakeZipTool(Tool):
    name = "make_zip"
    description = "Package the entire current session workspace (all generated files/code/images) into a downloadable .zip archive."
    parameters = {
        "type": "object",
        "properties": {"zip_name": {"type": "string", "description": "Name for the zip (without extension)", "default": "meiko_export"}},
        "required": [],
    }

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, zip_name: str = "meiko_export", **_: Any) -> str:
        session_id = self._session_id_provider()
        src = _workspace_root(session_id)
        exports = _exports_root(session_id)
        stamp = int(time.time())
        safe_name = "".join(c for c in zip_name if c.isalnum() or c in ("-", "_")) or "meiko_export"
        archive_base = exports / f"{safe_name}_{stamp}"
        archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(src))
        rel = Path(archive_path).relative_to(Path(get_settings().DATA_DIR))
        return f"Created zip archive: {rel} — download via /api/download/{session_id}/{Path(archive_path).name}"
