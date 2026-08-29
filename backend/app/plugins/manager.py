"""
ConnectorManager — discovers manifests from backend/plugins/*.json,
resolves auth secrets (from env or per-user stored keys), and exposes
them as Tools that get merged into the harness's ToolRegistry.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .base import ConnectorActionTool, ConnectorManifest

PLUGINS_DIR = Path(__file__).resolve().parent.parent.parent / "plugins"


class ConnectorManager:
    def __init__(self, plugins_dir: Path = PLUGINS_DIR):
        self.plugins_dir = plugins_dir
        self._manifests: dict[str, ConnectorManifest] = {}
        self.reload()

    def reload(self) -> None:
        self._manifests.clear()
        if not self.plugins_dir.exists():
            return
        for file in sorted(self.plugins_dir.glob("*.json")):
            try:
                manifest = ConnectorManifest.from_json_file(str(file))
                self._manifests[manifest.id] = manifest
            except Exception as e:  # noqa: BLE001
                print(f"[ConnectorManager] Failed to load {file}: {e}")

    def register_manifest(self, data: dict[str, Any]) -> ConnectorManifest:
        manifest = ConnectorManifest.from_dict(data)
        self._manifests[manifest.id] = manifest
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        with open(self.plugins_dir / f"{manifest.id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return manifest

    def list_manifests(self) -> list[ConnectorManifest]:
        return list(self._manifests.values())

    def get(self, connector_id: str) -> Optional[ConnectorManifest]:
        return self._manifests.get(connector_id)

    def set_enabled(self, connector_id: str, enabled: bool) -> None:
        if connector_id in self._manifests:
            self._manifests[connector_id].enabled = enabled

    def build_tools(self, user_secrets: Optional[dict[str, str]] = None) -> list[ConnectorActionTool]:
        """Return ConnectorActionTool instances for all enabled connectors,
        with auth values resolved from user_secrets (by connector id) or env vars."""
        user_secrets = user_secrets or {}
        tools: list[ConnectorActionTool] = []
        for manifest in self._manifests.values():
            if not manifest.enabled:
                continue
            if manifest.auth.type != "none":
                secret = user_secrets.get(manifest.id) or os.environ.get(f"CONNECTOR_{manifest.id.upper()}_KEY")
                manifest.auth.value = secret
            for action in manifest.actions:
                tools.append(ConnectorActionTool(manifest, action))
        return tools


_manager: Optional[ConnectorManager] = None


def get_connector_manager() -> ConnectorManager:
    global _manager
    if _manager is None:
        _manager = ConnectorManager()
    return _manager
