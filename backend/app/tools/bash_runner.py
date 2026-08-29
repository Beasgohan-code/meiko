"""
Sandboxed bash runner — gives Meiko a real shell inside its per-session
workspace, mirroring Claude Code / DeepSeek-harness "bash tool" behavior.

Safety:
  - Executes via `/bin/bash -lc "<command>"` in a subprocess, cwd pinned to
    the session workspace directory (never the host root).
  - Hard timeout (default 20s, max 120s) to prevent runaway/hanging jobs.
  - Output is truncated to keep responses small.
  - A configurable denylist blocks obviously destructive patterns
    (fork bombs, wiping the root fs, etc.) as a best-effort guard — this is
    NOT a full sandbox/jail, so only run Meiko in environments where the
    workspace directory itself is disposable (e.g. containers), same as
    the existing run_python tool.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from .base import Tool

_DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/(?:\s|$)",
    r"rm\s+-rf\s+~(?:\s|$)",
    r"rm\s+-rf\s+\*(?:\s|$)",
    r"mkfs\.",
    r":\(\)\s*\{\s*:\|:&\s*\};:",  # classic fork bomb
    r">\s*/dev/sd[a-z]",
    r"dd\s+.*of=/dev/",
    r"chmod\s+-R\s+000\s+/",
]


def _workspace_root(session_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.DATA_DIR) / "workspaces" / session_id
    root.mkdir(parents=True, exist_ok=True)
    return root


class BashRunTool(Tool):
    name = "run_bash"
    description = (
        "Execute a shell/bash command inside your sandboxed session workspace and return stdout/stderr. "
        "Use this for things run_python can't do directly: installing a small package, running git commands, "
        "listing/moving files, running a build/test script, curling a URL, unzip/zip operations, checking tool "
        "versions, etc. Runs with a timeout (default 20s, max 120s) and is scoped to your workspace directory. "
        "Avoid destructive or system-wide commands — you only have access to your own sandbox, not the host."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run, e.g. 'git clone ... && ls -la'"},
            "timeout_seconds": {"type": "integer", "description": "Max seconds to run (default 20, max 120)", "default": 20},
        },
        "required": ["command"],
    }

    def __init__(self, session_id_provider):
        self._session_id_provider = session_id_provider

    async def run(self, command: str, timeout_seconds: int = 20, **_: Any) -> str:
        session_id = self._session_id_provider()
        root = _workspace_root(session_id)
        timeout_seconds = min(max(int(timeout_seconds or 20), 1), 120)

        for pattern in _DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return (
                    "Error: this command was blocked by Meiko's safety guard (looks destructive or "
                    "system-wide). Please use a narrower, workspace-scoped command."
                )

        try:
            proc = await asyncio.create_subprocess_exec(
                "/bin/bash", "-lc", command,
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                proc.kill()
                return f"Error: command timed out after {timeout_seconds}s"
        except Exception as e:  # noqa: BLE001
            return f"Error launching shell: {e}"

        out = stdout.decode(errors="replace")[:6000]
        err = stderr.decode(errors="replace")[:3000]
        result = f"exit_code={proc.returncode}\n--- stdout ---\n{out or '(empty)'}"
        if err:
            result += f"\n--- stderr ---\n{err}"
        return result
