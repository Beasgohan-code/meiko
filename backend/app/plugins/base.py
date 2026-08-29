"""
Meiko Plugin/Connector Framework
=================================
Inspired by Claude's "Connectors" and DeepSeek-harness style plugin systems.

A "connector" is a JSON manifest describing an external HTTP API as a set
of callable tools — no Python code required to add a new integration.
Drop a manifest into `backend/plugins/*.json` (or POST one via the API)
and Meiko can immediately call it as a tool.

Manifest shape:
{
  "id": "github",
  "name": "GitHub",
  "description": "Query public GitHub repos and code search",
  "base_url": "https://api.github.com",
  "auth": {"type": "bearer", "header": "Authorization", "env_key": "GITHUB_TOKEN"},
  "actions": [
    {
      "name": "github_search_repos",
      "description": "Search public GitHub repositories",
      "method": "GET",
      "path": "/search/repositories",
      "parameters": {
        "type": "object",
        "properties": {"q": {"type": "string"}, "per_page": {"type": "integer", "default": 5}},
        "required": ["q"]
      },
      "query_params": ["q", "per_page"]
    }
  ]
}
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from ..tools.base import Tool


@dataclass
class ConnectorAuth:
    type: str = "none"  # none | bearer | api_key_header | api_key_query
    header: str = "Authorization"
    query_param: str = "api_key"
    prefix: str = "Bearer "
    value: Optional[str] = None  # resolved secret (from user settings or env)


@dataclass
class ConnectorAction:
    name: str
    description: str
    method: str
    path: str
    parameters: dict[str, Any]
    query_params: list[str] = field(default_factory=list)
    body_params: list[str] = field(default_factory=list)
    path_params: list[str] = field(default_factory=list)


@dataclass
class ConnectorManifest:
    id: str
    name: str
    description: str
    base_url: str
    auth: ConnectorAuth
    actions: list[ConnectorAction]
    enabled: bool = True

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ConnectorManifest":
        auth_d = d.get("auth", {}) or {}
        auth = ConnectorAuth(
            type=auth_d.get("type", "none"),
            header=auth_d.get("header", "Authorization"),
            query_param=auth_d.get("query_param", "api_key"),
            prefix=auth_d.get("prefix", "Bearer "),
        )
        actions = [
            ConnectorAction(
                name=a["name"],
                description=a.get("description", ""),
                method=a.get("method", "GET").upper(),
                path=a["path"],
                parameters=a.get("parameters", {"type": "object", "properties": {}, "required": []}),
                query_params=a.get("query_params", []),
                body_params=a.get("body_params", []),
                path_params=a.get("path_params", []),
            )
            for a in d.get("actions", [])
        ]
        return ConnectorManifest(
            id=d["id"], name=d.get("name", d["id"]), description=d.get("description", ""),
            base_url=d["base_url"].rstrip("/"), auth=auth, actions=actions, enabled=d.get("enabled", True),
        )

    @staticmethod
    def from_json_file(path: str) -> "ConnectorManifest":
        with open(path, "r", encoding="utf-8") as f:
            return ConnectorManifest.from_dict(json.load(f))


class ConnectorActionTool(Tool):
    """Wraps a single ConnectorAction as a callable Tool for the harness."""

    def __init__(self, manifest: ConnectorManifest, action: ConnectorAction):
        self.manifest = manifest
        self.action = action
        self.name = action.name
        self.description = f"[{manifest.name} connector] {action.description}"
        self.parameters = action.parameters

    def _auth_headers(self) -> dict[str, str]:
        auth = self.manifest.auth
        if auth.type == "bearer" and auth.value:
            return {auth.header: f"{auth.prefix}{auth.value}"}
        if auth.type == "api_key_header" and auth.value:
            return {auth.header: auth.value}
        return {}

    def _auth_query(self) -> dict[str, str]:
        auth = self.manifest.auth
        if auth.type == "api_key_query" and auth.value:
            return {auth.query_param: auth.value}
        return {}

    async def run(self, **kwargs: Any) -> str:
        path = self.action.path
        for p in self.action.path_params:
            if p in kwargs:
                path = path.replace(f"{{{p}}}", str(kwargs.pop(p)))

        query = {k: v for k, v in kwargs.items() if k in self.action.query_params}
        body = {k: v for k, v in kwargs.items() if k in self.action.body_params}
        query.update(self._auth_query())

        url = f"{self.manifest.base_url}{path}"
        headers = {"Accept": "application/json", **self._auth_headers()}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(self.action.method, url, params=query, json=body or None, headers=headers)
                text = resp.text
                if resp.status_code >= 400:
                    return f"Connector '{self.manifest.id}' action '{self.name}' failed ({resp.status_code}): {text[:500]}"
                return text[:6000]
        except Exception as e:  # noqa: BLE001
            return f"Connector '{self.manifest.id}' action '{self.name}' error: {e}"
