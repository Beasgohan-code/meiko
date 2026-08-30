"""
Meiko Tools Generator — lets a user (via the hidden dev-mode panel) describe
a new tool in plain terms and get back a real, callable Tool the agent can
use immediately, without writing/deploying a Python file by hand.

Two flavors, matching how most "give the agent a new capability" requests
actually look in practice:

  - kind="http": call a REST endpoint. You give a URL template with
    {placeholders} that get filled from the tool's arguments (e.g.
    "https://api.example.com/search?q={query}"), an HTTP method, and
    optional headers (e.g. a bearer token) — Meiko builds a working Tool
    around httpx with no code at all. This covers the overwhelming
    majority of "hook up API X" requests, and is exactly the same shape
    the existing JSON-manifest connector system already trusts.

  - kind="python": a short Python function BODY (not a whole file) that
    receives its declared arguments as local variables and should set a
    variable named `result` (str) with what the tool should return. This
    runs through the exact same sandboxed subprocess mechanism as the
    agent's own run_python tool (own process, workspace-scoped cwd,
    timeout) — never `exec()`'d in-process — so a bad/malicious body can't
    touch the server, only its own throwaway workspace.

Generated tools are persisted as JSON under `backend/data/custom_tools/` (or
DATA_DIR/custom_tools/) so they survive a server restart, and are merged
into the harness's ToolRegistry alongside the built-ins and connectors.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from ..core.config import get_settings
from .base import Tool

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# Reserve every built-in/harness tool name so a generated tool can never
# silently shadow (and thus disable) a real one.
_RESERVED_NAMES = {
    "web_search", "fetch_url", "calculator", "write_file", "read_file", "list_files",
    "run_python", "run_bash", "generate_image", "make_document", "make_zip",
    "remember", "recall_memories", "update_plan", "list_skills", "use_skill",
    "github_search_repos", "github_list_files", "github_read_file", "github_write_file",
    "github_create_issue", "github_create_pull_request", "github_list_issues",
}


def _custom_tools_dir() -> Path:
    settings = get_settings()
    d = Path(settings.DATA_DIR) / "custom_tools"
    d.mkdir(parents=True, exist_ok=True)
    return d


class CustomToolValidationError(ValueError):
    pass


@dataclass
class CustomToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    kind: str  # "http" | "python"
    http_method: str = "GET"
    http_url_template: Optional[str] = None
    http_headers: dict[str, str] = field(default_factory=dict)
    python_body: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "kind": self.kind,
            "http_method": self.http_method,
            "http_url_template": self.http_url_template,
            "http_headers": self.http_headers,
            "python_body": self.python_body,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CustomToolSpec":
        return CustomToolSpec(
            name=d["name"],
            description=d.get("description", ""),
            parameters=d.get("parameters") or {"type": "object", "properties": {}, "required": []},
            kind=d.get("kind", "http"),
            http_method=d.get("http_method", "GET"),
            http_url_template=d.get("http_url_template"),
            http_headers=d.get("http_headers") or {},
            python_body=d.get("python_body"),
            created_at=d.get("created_at", time.time()),
        )


def validate_spec(
    name: str,
    description: str,
    parameters: dict[str, Any],
    kind: str,
    http_method: str = "GET",
    http_url_template: Optional[str] = None,
    http_headers: Optional[dict[str, str]] = None,
    python_body: Optional[str] = None,
) -> CustomToolSpec:
    if not _NAME_RE.fullmatch(name or ""):
        raise CustomToolValidationError(
            "Tool name must start with a lowercase letter and contain only lowercase letters, digits, and underscores"
        )
    if name in _RESERVED_NAMES:
        raise CustomToolValidationError(f"'{name}' is a built-in tool name and can't be overridden")
    if not description.strip():
        raise CustomToolValidationError("Description is required (the agent uses it to decide when to call this tool)")
    if kind not in ("http", "python"):
        raise CustomToolValidationError("kind must be 'http' or 'python'")
    if kind == "http":
        if not http_url_template or not http_url_template.strip():
            raise CustomToolValidationError("http_url_template is required for kind='http'")
        if not http_url_template.startswith(("http://", "https://")):
            raise CustomToolValidationError("http_url_template must be an absolute http(s) URL")
    if kind == "python" and not (python_body or "").strip():
        raise CustomToolValidationError("python_body is required for kind='python'")
    if not isinstance(parameters, dict) or parameters.get("type") not in (None, "object"):
        raise CustomToolValidationError("parameters must be a JSON-schema object (type: 'object')")
    parameters = {
        "type": "object",
        "properties": parameters.get("properties", {}),
        "required": parameters.get("required", []),
    }
    return CustomToolSpec(
        name=name, description=description.strip(), parameters=parameters, kind=kind,
        http_method=(http_method or "GET").upper(), http_url_template=http_url_template,
        http_headers=http_headers or {}, python_body=python_body,
    )


def save_custom_tool(spec: CustomToolSpec) -> CustomToolSpec:
    path = _custom_tools_dir() / f"{spec.name}.json"
    path.write_text(json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    return spec


def delete_custom_tool(name: str) -> bool:
    if not _NAME_RE.fullmatch(name or ""):
        raise CustomToolValidationError("Invalid tool name")
    path = _custom_tools_dir() / f"{name}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def list_custom_tool_specs() -> list[CustomToolSpec]:
    specs = []
    for f in sorted(_custom_tools_dir().glob("*.json")):
        try:
            specs.append(CustomToolSpec.from_dict(json.loads(f.read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001
            continue
    return specs


def get_custom_tool_spec(name: str) -> Optional[CustomToolSpec]:
    for s in list_custom_tool_specs():
        if s.name == name:
            return s
    return None


class GeneratedHttpTool(Tool):
    """A Tool whose behavior is 'fill this URL template and call it' —
    generated from a CustomToolSpec, no bespoke Python needed."""

    def __init__(self, spec: CustomToolSpec):
        self.name = spec.name
        self.description = f"[custom tool] {spec.description}"
        self.parameters = spec.parameters
        self._spec = spec

    async def run(self, **kwargs: Any) -> str:
        spec = self._spec
        try:
            url = spec.http_url_template.format(**{k: str(v) for k, v in kwargs.items()})
        except KeyError as e:
            return f"Error: missing argument {e} needed to build the URL"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                if spec.http_method in ("POST", "PUT", "PATCH"):
                    resp = await client.request(spec.http_method, url, headers=spec.http_headers, json=kwargs)
                else:
                    resp = await client.request(spec.http_method, url, headers=spec.http_headers)
            text = resp.text[:4000]
            return f"HTTP {resp.status_code}\n{text}"
        except Exception as e:  # noqa: BLE001
            return f"Error calling custom tool '{spec.name}': {e}"


class GeneratedPythonTool(Tool):
    """A Tool whose behavior is a short Python body run in its own
    subprocess (same sandboxing posture as run_python) — the tool's
    declared arguments are injected as JSON-decoded local variables, and
    whatever the body assigns to `result` is returned as the tool output."""

    def __init__(self, spec: CustomToolSpec, session_id_provider):
        self.name = spec.name
        self.description = f"[custom tool] {spec.description}"
        self.parameters = spec.parameters
        self._spec = spec
        self._session_id_provider = session_id_provider

    async def run(self, **kwargs: Any) -> str:
        from ..core.config import get_settings

        settings = get_settings()
        session_id = self._session_id_provider()
        root = Path(settings.DATA_DIR) / "workspaces" / Path(session_id).name
        root.mkdir(parents=True, exist_ok=True)

        args_json = json.dumps(kwargs)
        script = (
            "import json\n"
            f"_args = json.loads({args_json!r})\n"
            "locals().update(_args)\n"
            "result = None\n"
            f"{self._spec.python_body}\n"
            "print('\\n__MEIKO_RESULT__\\n' + (result if isinstance(result, str) else json.dumps(result)))\n"
        )
        script_path = root / f"_custom_tool_{self._spec.name}.py"
        script_path.write_text(script, encoding="utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path), cwd=str(root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            except asyncio.TimeoutError:
                proc.kill()
                return "Error: custom tool timed out after 15s"
        except Exception as e:  # noqa: BLE001
            return f"Error launching custom tool: {e}"

        out = stdout.decode(errors="replace")
        if proc.returncode != 0:
            return f"Error running custom tool '{self._spec.name}':\n{stderr.decode(errors='replace')[:2000]}"
        marker = "__MEIKO_RESULT__\n"
        if marker in out:
            return out.split(marker, 1)[1].strip()[:4000]
        return out.strip()[:4000] or "(no output)"


def build_custom_tools(session_id_provider) -> list[Tool]:
    """Instantiate every saved custom tool spec as a real Tool, ready to
    merge into the harness's ToolRegistry."""
    tools: list[Tool] = []
    for spec in list_custom_tool_specs():
        if spec.kind == "http":
            tools.append(GeneratedHttpTool(spec))
        else:
            tools.append(GeneratedPythonTool(spec, session_id_provider))
    return tools
