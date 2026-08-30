from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(default="default", max_length=128)
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=12000)
    provider: Optional[str] = None
    model: Optional[str] = None
    mode: str = "autonomous"
    persona: Optional[str] = None
    persona_id: Optional[str] = None
    image_paths: Optional[list[str]] = None
    enable_fallback: bool = True
    ui_language: Optional[str] = None  # e.g. "es", "hi", "fr" — nudges the agent to reply in this language


class SettingsUpdateRequest(BaseModel):
    user_id: str = Field(default="default", max_length=128)
    provider: Optional[str] = None
    model: Optional[str] = None
    persona: Optional[str] = None
    api_keys: Optional[dict[str, str]] = None
    theme: Optional[str] = None
    ui_language: Optional[str] = None


class NewConversationRequest(BaseModel):
    user_id: str = Field(default="default", max_length=128)
    title: str = Field(default="", max_length=200)


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class ConnectorManifestRequest(BaseModel):
    manifest: dict


class ConnectorToggleRequest(BaseModel):
    enabled: bool


class ConnectorSecretRequest(BaseModel):
    user_id: str = Field(default="default", max_length=128)
    secret: str


class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    triggers: list[str] = Field(default_factory=list)
    body: str = Field(..., min_length=1, max_length=50000)
    skill_id: Optional[str] = Field(default=None, max_length=100)


class PairingCreateRequest(BaseModel):
    user_id: str = Field(default="default", max_length=128)


class PairingClaimRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=12)


class MemoryCreateRequest(BaseModel):
    user_id: str = Field(default="default", max_length=128)
    fact: str = Field(..., min_length=1, max_length=2000)
