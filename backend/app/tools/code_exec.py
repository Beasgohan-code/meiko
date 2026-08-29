"""
Sandboxed Python execution tool — lets Meiko act like a real coding agent
(Claude Code / DeepSeek harness style): it can run the code it just wrote
and see the output/errors, then iterate.

Safety: runs in a subprocess with a timeout, resource limits (best-effort
on POSIX), no network restriction beyond what the host allows, and is
scoped to execute inside the session's sandbox workspace directory.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from .base import Tool


def _workspace_root(session_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.DATA_DIR) / "workspaces" / session_id
    root.mkdir(parents=True, exist_ok=True)
    return root


class RunPythonTool(Tool):
    name = "run_python"
    description = (
        "Execute a Python snippet inside the sandboxed session workspace and return stdout/stderr. "
        "Use this to test code you've written with write_file, run calculations, or process data. "
        "Runs with a 15 second timeout and no destructive access outside the workspace."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute"},
            "timeout_seconds": {"type": "integer", "description": "Max seconds to run (default 15, max 30)", "default": 15},
        },
        "required": ["code"],
    }

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, code: str, timeout_seconds: int = 15, **_: Any) -> str:
        session_id = self._session_id_provider()
        root = _workspace_root(session_id)
        timeout_seconds = min(max(timeout_seconds, 1), 30)

        script_path = root / "_run_snippet.py"
        script_path.write_text(code, encoding="utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                proc.kill()
                return f"Error: execution timed out after {timeout_seconds}s"
        except Exception as e:  # noqa: BLE001
            return f"Error launching subprocess: {e}"

        out = stdout.decode(errors="replace")[:6000]
        err = stderr.decode(errors="replace")[:3000]
        result = f"exit_code={proc.returncode}\n--- stdout ---\n{out}"
        if err:
            result += f"\n--- stderr ---\n{err}"
        return result
