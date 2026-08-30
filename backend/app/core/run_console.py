"""
Meiko Dev Console — an arena.ai / menus.ai-style "run a command, watch it
stream live, inspect the output" surface, independent of the chat harness.

Unlike the agent's own `run_bash`/`run_python` tools (bash_runner.py,
code_exec.py), which block until the subprocess finishes and hand the LLM
one final text blob, this module keeps a *live* buffer per run that a
client can poll incrementally (mirroring the `get_process_output` tool
pattern this project already uses to talk to sandboxes: tail_lines,
wait_for, wait_timeout) or subscribe to over a WebSocket for real-time
push — so a UI can render an actual terminal instead of a spinner.

Design:
  - `RunManager.start()` launches a subprocess (bash script or a python
    file), cwd pinned to the session's sandbox workspace (same directory
    convention as bash_runner/code_exec), merges stdout+stderr into one
    ordered stream (real terminals interleave them; splitting loses the
    interleaving), and reads it in small chunks (not lines) so partial
    output like progress bars/prompts shows up immediately rather than
    only once a newline arrives.
  - Every run keeps a capped in-memory buffer (default 256 KB tail) plus a
    monotonic cursor so `get_output(run_id, since=N)` is a cheap, correct
    "give me what's new since my last poll" — the same shape as this
    project's own `get_process_output` sandbox tool.
  - `get_output(..., wait_for="exit"|"log", wait_pattern=..., wait_timeout=...)`
    lets a client block briefly for a condition instead of tight-polling,
    again mirroring `get_process_output`.
  - A tiny per-run pub/sub (reusing the pattern from core/sync.py's
    SyncHub) lets a WebSocket client get pushed new bytes the instant
    they're produced, for a truly live terminal feel.
  - Runs are session-scoped and capped in count/lifetime so this can't
    leak processes or memory in a long-lived server process.
"""
from __future__ import annotations

import asyncio
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .config import get_settings

_MAX_BUFFER_BYTES = 256 * 1024  # keep the tail; drop the oldest bytes beyond this
_MAX_RUNS_PER_SESSION = 20  # oldest finished runs are evicted beyond this
_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 300

_DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/(?:\s|$)",
    r"rm\s+-rf\s+~(?:\s|$)",
    r"rm\s+-rf\s+\*(?:\s|$)",
    r"mkfs\.",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r">\s*/dev/sd[a-z]",
    r"dd\s+.*of=/dev/",
    r"chmod\s+-R\s+000\s+/",
]


def is_dangerous(command: str) -> bool:
    return any(re.search(p, command) for p in _DANGEROUS_PATTERNS)


def workspace_root(session_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.DATA_DIR) / "workspaces" / Path(session_id).name
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass
class Run:
    id: str
    session_id: str
    command: str
    kind: str  # "bash" | "python"
    status: str = "running"  # running | exited | killed | timeout | error
    exit_code: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    buffer: bytearray = field(default_factory=bytearray)
    cursor_base: int = 0  # bytes dropped from the front of `buffer` so far
    proc: Optional[asyncio.subprocess.Process] = None
    task: Optional[asyncio.Task] = None
    subscribers: set[asyncio.Queue] = field(default_factory=set)

    def total_len(self) -> int:
        return self.cursor_base + len(self.buffer)

    def append(self, chunk: bytes) -> None:
        self.buffer.extend(chunk)
        if len(self.buffer) > _MAX_BUFFER_BYTES:
            drop = len(self.buffer) - _MAX_BUFFER_BYTES
            del self.buffer[:drop]
            self.cursor_base += drop
        for q in list(self.subscribers):
            try:
                q.put_nowait(chunk)
            except asyncio.QueueFull:
                pass

    def slice_since(self, since: int) -> tuple[str, int]:
        """Returns (new_text, new_cursor). `since` may be stale (older than
        what we've retained) — in that case we just return everything we
        still have, same "best effort" spirit as get_process_output."""
        start = max(0, since - self.cursor_base)
        data = bytes(self.buffer[start:])
        return data.decode(errors="replace"), self.total_len()

    def to_summary(self) -> dict[str, Any]:
        return {
            "run_id": self.id,
            "session_id": self.session_id,
            "command": self.command,
            "kind": self.kind,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def _evict_old(self, session_id: str) -> None:
        finished = [
            r for r in self._runs.values()
            if r.session_id == session_id and r.status != "running"
        ]
        finished.sort(key=lambda r: r.started_at)
        while len(finished) > _MAX_RUNS_PER_SESSION:
            oldest = finished.pop(0)
            self._runs.pop(oldest.id, None)

    async def start(self, session_id: str, command: str, kind: str = "bash", timeout_seconds: int = _DEFAULT_TIMEOUT) -> Run:
        if kind not in ("bash", "python"):
            raise ValueError("kind must be 'bash' or 'python'")
        if kind == "bash" and is_dangerous(command):
            raise PermissionError(
                "This command was blocked by Meiko's safety guard (looks destructive or system-wide)."
            )
        timeout_seconds = min(max(int(timeout_seconds or _DEFAULT_TIMEOUT), 1), _MAX_TIMEOUT)
        root = workspace_root(session_id)

        run = Run(id=uuid.uuid4().hex, session_id=session_id, command=command, kind=kind)
        self._runs[run.id] = run
        self._evict_old(session_id)

        if kind == "python":
            script_path = root / f"_console_{run.id}.py"
            script_path.write_text(command, encoding="utf-8")
            argv = [sys.executable, "-u", str(script_path)]
            proc = await asyncio.create_subprocess_exec(
                *argv, cwd=str(root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "/bin/bash", "-lc", command, cwd=str(root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
        run.proc = proc
        run.task = asyncio.create_task(self._pump(run, timeout_seconds))
        return run

    async def _pump(self, run: Run, timeout_seconds: int) -> None:
        assert run.proc is not None and run.proc.stdout is not None
        deadline = time.time() + timeout_seconds
        try:
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    run.proc.kill()
                    run.status = "timeout"
                    run.append(f"\n[Meiko] timed out after {timeout_seconds}s, process killed\n".encode())
                    break
                try:
                    chunk = await asyncio.wait_for(run.proc.stdout.read(4096), timeout=min(remaining, 1.0))
                except asyncio.TimeoutError:
                    continue
                if not chunk:
                    break
                run.append(chunk)
            if run.status == "running":
                run.exit_code = await run.proc.wait()
                run.status = "exited"
        except Exception as e:  # noqa: BLE001
            run.status = "error"
            run.append(f"\n[Meiko] error: {e}\n".encode())
        finally:
            run.finished_at = time.time()
            for q in list(run.subscribers):
                try:
                    q.put_nowait(None)  # sentinel: stream closed
                except asyncio.QueueFull:
                    pass

    def get(self, run_id: str) -> Optional[Run]:
        return self._runs.get(run_id)

    def list_for_session(self, session_id: str) -> list[Run]:
        return sorted(
            (r for r in self._runs.values() if r.session_id == session_id),
            key=lambda r: r.started_at, reverse=True,
        )

    async def stop(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if not run or run.status != "running" or not run.proc:
            return False
        run.proc.kill()
        run.status = "killed"
        if run.task and not run.task.done():
            try:
                await asyncio.wait_for(run.task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        return True

    async def get_output(
        self,
        run_id: str,
        since: int = 0,
        wait_for: Optional[str] = None,
        wait_pattern: Optional[str] = None,
        wait_timeout: float = 20.0,
    ) -> dict[str, Any]:
        """Mirrors the shape/semantics of this project's `get_process_output`
        sandbox tool: `wait_for` is 'exit' (block until the process exits)
        or 'log' (block until new output matches `wait_pattern`), else
        return immediately with whatever's new since `since`."""
        run = self._runs.get(run_id)
        if not run:
            raise KeyError(run_id)

        deadline = time.time() + max(1.0, min(wait_timeout, 120.0))
        compiled = re.compile(wait_pattern) if (wait_for == "log" and wait_pattern) else None

        while True:
            text, cursor = run.slice_since(since)
            wait_result = "immediate"
            condition_met = wait_for is None
            if wait_for == "exit" and run.status != "running":
                condition_met = True
                wait_result = "matched"
            elif wait_for == "log" and compiled and compiled.search(text):
                condition_met = True
                wait_result = "matched"
            elif wait_for and run.status != "running":
                # process ended without ever matching a 'log' condition
                condition_met = True
                wait_result = "exited"

            if condition_met or time.time() >= deadline:
                if wait_for and not condition_met:
                    wait_result = "timeout"
                return {
                    **run.to_summary(),
                    "output": text,
                    "cursor": cursor,
                    "wait_result": wait_result if wait_for else None,
                }
            await asyncio.sleep(0.25)


_manager: Optional[RunManager] = None


def get_run_manager() -> RunManager:
    global _manager
    if _manager is None:
        _manager = RunManager()
    return _manager
