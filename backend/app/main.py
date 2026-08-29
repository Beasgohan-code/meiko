"""
Meiko Agent — FastAPI Backend Entrypoint

Exposes:
  - POST /api/chat/stream  -> SSE stream of agent thinking/tool/final events
  - GET  /api/conversations, /api/conversations/{id}/messages
  - GET/POST /api/settings -> per-user provider + API key + persona config
  - GET  /api/providers    -> provider catalog for Settings UI
  - GET  /api/modes        -> agent mode catalog
  - GET/POST /api/connectors -> plugin/connector management
  - POST /api/upload       -> upload an image/document into a session workspace
  - GET  /api/download/{session_id}/{filename} -> download generated files/zip
  - GET  /health
"""
from __future__ import annotations

import base64
import mimetypes
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .api.schemas import (
    ChatRequest,
    ConnectorManifestRequest,
    ConnectorToggleRequest,
    NewConversationRequest,
    SettingsUpdateRequest,
)
from .core.config import get_settings
from .core.modes import list_modes
from .harness.agent import AgentEvent, MeikoAgent
from .memory.store import get_store
from .plugins.manager import get_connector_manager
from .providers.base import ChatMessage
from .providers.registry import list_provider_meta

settings = get_settings()
app = FastAPI(title="Meiko Agent API", version="1.0.0")

origins = ["*"] if settings.CORS_ORIGINS.strip() == "*" else [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    await get_store().init()


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/api/providers")
async def get_providers():
    return [meta.__dict__ for meta in list_provider_meta()]


@app.get("/api/modes")
async def get_modes():
    return [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "icon": m.icon,
            "max_steps": m.max_steps,
        }
        for m in list_modes()
    ]


# ---------------- Settings ----------------
@app.get("/api/settings")
async def get_settings_route(user_id: str = Query("default")):
    store = get_store()
    data = await store.get_user_settings(user_id)
    # never leak full API keys back to client; mask them
    masked = {}
    for k, v in data["api_keys"].items():
        masked[k] = (v[:4] + "…" + v[-2:]) if v and len(v) > 8 else ("set" if v else "")
    data["api_keys_masked"] = masked
    data.pop("api_keys", None)
    return data


@app.post("/api/settings")
async def update_settings_route(payload: SettingsUpdateRequest):
    store = get_store()
    await store.set_user_settings(
        payload.user_id, provider=payload.provider, model=payload.model,
        api_keys=payload.api_keys, persona=payload.persona,
    )
    return {"ok": True}


# ---------------- Conversations ----------------
@app.post("/api/conversations")
async def create_conversation(payload: NewConversationRequest):
    store = get_store()
    conv_id = await store.create_conversation(payload.user_id, payload.title)
    return {"conversation_id": conv_id}


@app.get("/api/conversations")
async def list_conversations(user_id: str = Query("default")):
    store = get_store()
    return await store.list_conversations(user_id)


@app.get("/api/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    store = get_store()
    return await store.get_messages(conversation_id)


# ---------------- Connectors / Plugins ----------------
@app.get("/api/connectors")
async def list_connectors():
    manager = get_connector_manager()
    return [
        {
            "id": m.id, "name": m.name, "description": m.description, "enabled": m.enabled,
            "requires_key": m.auth.type != "none",
            "actions": [a.name for a in m.actions],
        }
        for m in manager.list_manifests()
    ]


@app.post("/api/connectors")
async def register_connector(payload: ConnectorManifestRequest):
    manager = get_connector_manager()
    manifest = manager.register_manifest(payload.manifest)
    return {"ok": True, "id": manifest.id}


@app.post("/api/connectors/{connector_id}/toggle")
async def toggle_connector(connector_id: str, payload: ConnectorToggleRequest):
    manager = get_connector_manager()
    manager.set_enabled(connector_id, payload.enabled)
    return {"ok": True}


# ---------------- Upload / Download ----------------
@app.post("/api/upload")
async def upload_file(session_id: str = Query(...), file: UploadFile = File(...)):
    root = Path(settings.DATA_DIR) / "workspaces" / session_id / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    dest = root / file.filename
    content = await file.read()
    dest.write_bytes(content)

    mime, _ = mimetypes.guess_type(file.filename)
    result: dict[str, str] = {"path": f"uploads/{file.filename}", "mime": mime or "application/octet-stream"}
    if mime and mime.startswith("image/"):
        b64 = base64.b64encode(content).decode()
        result["data_url"] = f"data:{mime};base64,{b64}"
    return result


@app.get("/api/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    # search both workspace and exports folders
    candidates = [
        Path(settings.DATA_DIR) / "exports" / session_id / filename,
        Path(settings.DATA_DIR) / "workspaces" / session_id / filename,
        Path(settings.DATA_DIR) / "workspaces" / session_id / "images" / filename,
    ]
    for path in candidates:
        if path.exists():
            return FileResponse(str(path), filename=filename)
    raise HTTPException(status_code=404, detail="File not found")


# ---------------- Chat (SSE streaming) ----------------
@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest):
    store = get_store()
    session_id = payload.session_id or payload.conversation_id or str(uuid.uuid4())

    conversation_id = payload.conversation_id
    if not conversation_id:
        conversation_id = await store.create_conversation(payload.user_id, title=payload.message[:60])

    user_settings = await store.get_user_settings(payload.user_id)
    provider_id = payload.provider or user_settings.get("provider") or settings.DEFAULT_PROVIDER
    model = payload.model or user_settings.get("model") or None
    api_key_override = user_settings.get("api_keys", {}).get(provider_id)
    persona = payload.persona or user_settings.get("persona") or None

    history_rows = await store.get_messages(conversation_id, limit=40)
    history: list[ChatMessage] = []
    for row in history_rows:
        if row["role"] in ("user", "assistant"):
            history.append(ChatMessage(role=row["role"], content=row["content"]))

    await store.add_message(conversation_id, "user", payload.message)

    image_urls = payload.image_paths or None

    agent = MeikoAgent(
        settings,
        provider_id=provider_id,
        model=model,
        api_key_override=api_key_override,
        persona_extra=persona,
        mode_id=payload.mode,
        connector_secrets=user_settings.get("api_keys", {}),
    )

    async def event_generator():
        final_text = ""
        try:
            async for event in agent.run(session_id, payload.user_id, history, payload.message, image_urls=image_urls):
                if event.type == "final":
                    final_text = event.data.get("text", "")
                yield event.to_sse()
        finally:
            if final_text:
                await store.add_message(conversation_id, "assistant", final_text)
                await store.touch_conversation(conversation_id)

        yield AgentEvent(type="done", data={"conversation_id": conversation_id, "session_id": session_id}).to_sse()

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


# Serve any static assets bundled with backend (e.g. built web app), optional.
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
