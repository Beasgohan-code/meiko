from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str = "default"
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message: str
    provider: Optional[str] = None
    model: Optional[str] = None
    mode: str = "autonomous"
    persona: Optional[str] = None
    image_paths: Optional[list[str]] = None


class SettingsUpdateRequest(BaseModel):
    user_id: str = "default"
    provider: Optional[str] = None
    model: Optional[str] = None
    persona: Optional[str] = None
    api_keys: Optional[dict[str, str]] = None


class NewConversationRequest(BaseModel):
    user_id: str = "default"
    title: str = ""


class ConnectorManifestRequest(BaseModel):
    manifest: dict


class ConnectorToggleRequest(BaseModel):
    enabled: bool
