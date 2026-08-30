"""
Meiko Agent — FastAPI Backend Entrypoint

Exposes:
  - POST /api/chat/stream  -> SSE stream of agent thinking/tool/final events
  - GET  /api/conversations, /api/conversations/{id}/messages
  - PATCH/DELETE /api/conversations/{id}, GET /api/conversations/search
  - GET/POST /api/settings -> per-user provider + API key + persona config
  - GET  /api/providers    -> provider catalog for Settings UI
  - GET  /api/modes        -> agent mode catalog
  - GET/POST /api/connectors -> plugin/connector management
  - POST /api/upload       -> upload an image/document into a session workspace
  - GET  /api/download/{session_id}/{filename} -> download generated files/zip
  - GET  /api/usage        -> per-user usage analytics summary
  - POST /api/sync/pair, POST /api/sync/claim, GET /api/sync/status,
    WS   /ws/sync/{user_id} -> cross-device pairing codes + live push so the
    web app, native Android app, Flutter app, Telegram bot, and CLI can all
    share one account and see each other's changes in real time
  - GET  /health, GET /health/ready

Cross-cutting concerns (structured logging, optional API-key auth, rate
limiting) are applied via middleware/dependencies — see core/logging.py and
core/security.py.
"""
from __future__ import annotations

import base64
import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .api.schemas import (
    ChatRequest,
    ConnectorManifestRequest,
    ConnectorToggleRequest,
    MemoryCreateRequest,
    NewConversationRequest,
    PairingClaimRequest,
    PairingCreateRequest,
    RenameConversationRequest,
    SettingsUpdateRequest,
)
from .core.config import get_settings
from .core.logging import get_logger, new_request_id, request_id_ctx, setup_logging
from .core.modes import list_modes
from .core.personas import get_persona, list_personas
from .tools.skills import discover_skills
from .core.security import enforce_chat_rate_limit, enforce_general_rate_limit, require_api_key
from .core.sync import get_pairing_registry, get_sync_hub
from .harness.agent import AgentEvent, MeikoAgent
from .memory.store import get_store
from .plugins.manager import get_connector_manager
from .providers.base import ChatMessage
from .providers.registry import list_provider_meta
from .providers.model_catalog import list_models

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = get_logger("meiko.api")

_process_started_at = time.time()

app = FastAPI(title="Meiko Agent API", version="2.0.0")

origins = ["*"] if settings.CORS_ORIGINS.strip() == "*" else [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Attach a correlation id to every request and log method/path/status/latency."""
    rid = new_request_id()
    token = request_id_ctx.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_error path=%s method=%s", request.url.path, request.method)
        request_id_ctx.reset(token)
        return JSONResponse(status_code=500, content={"error": "internal_server_error", "request_id": rid})
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    logger.info(
        "%s %s -> %s (%sms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    request_id_ctx.reset(token)
    return response


@app.on_event("startup")
async def on_startup() -> None:
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    await get_store().init()
    backend = "postgresql" if getattr(settings, "DATABASE_URL", None) else "sqlite"
    logger.info(
        "Meiko backend startup complete (data_dir=%s, default_provider=%s, store=%s)",
        settings.DATA_DIR, settings.DEFAULT_PROVIDER, backend,
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    store = get_store()
    close = getattr(store, "close", None)
    if close is not None:
        await close()


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/health/ready")
async def health_ready():
    """Deeper readiness check: confirms the DB is reachable."""
    try:
        store = get_store()
        await store.list_conversations("__health_check__")
        return {"status": "ready"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"not ready: {e}")


@app.get("/api/system/status")
async def system_status():
    """Lightweight health/observability snapshot for the web app's Health tab
    (inspired by OmniRoute's Health Dashboard) — store backend, DB
    reachability, provider/connector/skill counts, and process uptime.
    Unlike OmniRoute this needs no separate metrics stack: it's a single
    cheap endpoint that reuses data Meiko already tracks."""
    db_ok = True
    db_error = None
    try:
        store = get_store()
        await store.list_conversations("__health_check__")
    except Exception as e:  # noqa: BLE001
        db_ok = False
        db_error = str(e)

    manager = get_connector_manager()
    manifests = manager.list_manifests()
    provider_metas = list_provider_meta()

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": app.version,
        "uptime_seconds": round(time.time() - _process_started_at, 1),
        "store": {
            "backend": "postgresql" if getattr(settings, "DATABASE_URL", None) else "sqlite",
            "reachable": db_ok,
            "error": db_error,
        },
        "providers": {
            "total": len(provider_metas),
            "free_tier": sum(1 for p in provider_metas if p.free_tier),
            "keyless": sum(1 for p in provider_metas if not p.requires_key),
        },
        "connectors": {
            "total": len(manifests),
            "enabled": sum(1 for m in manifests if m.enabled),
            "tool_count": sum(len(m.actions) for m in manifests),
        },
        "skills": len(discover_skills()),
        "default_provider": settings.DEFAULT_PROVIDER,
        "embeddings_enabled": bool(getattr(settings, "EMBEDDINGS_PROVIDER", None)),
    }


@app.get("/api/providers")
async def get_providers():
    return [meta.__dict__ for meta in list_provider_meta()]


@app.get("/api/models")
async def get_models(provider: str = Query("nvidia")):
    return [m.__dict__ for m in list_models(provider)]


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


@app.get("/api/personas")
async def get_personas():
    return [
        {"id": p.id, "name": p.name, "tagline": p.tagline}
        for p in list_personas()
    ]


@app.get("/api/skills")
async def get_skills():
    return [
        {"id": s.id, "name": s.name, "description": s.description, "triggers": s.triggers}
        for s in discover_skills()
    ]


@app.get("/api/skills/{skill_id}")
async def get_skill_detail(skill_id: str):
    for s in discover_skills():
        if s.id == skill_id:
            return {"id": s.id, "name": s.name, "description": s.description, "triggers": s.triggers, "body": s.body}
    raise HTTPException(status_code=404, detail=f"No skill named '{skill_id}'")


# ---------------- Settings ----------------
@app.get("/api/settings", dependencies=[Depends(require_api_key)])
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


@app.post("/api/settings", dependencies=[Depends(require_api_key)])
async def update_settings_route(payload: SettingsUpdateRequest):
    store = get_store()
    await store.set_user_settings(
        payload.user_id, provider=payload.provider, model=payload.model,
        api_keys=payload.api_keys, persona=payload.persona, ui_language=payload.ui_language,
    )
    await get_sync_hub().publish(payload.user_id, "settings_updated")
    return {"ok": True}


# ---------------- Cross-device sync (pairing + live push) ----------------
@app.post("/api/sync/pair", dependencies=[Depends(require_api_key)])
async def create_pairing_code(payload: PairingCreateRequest):
    """Device A calls this to mint a short-lived 6-character code that another
    device can type in to adopt the same `user_id` — the simplest possible
    account-free way to make two installs share conversations/settings/memory."""
    return get_pairing_registry().create(payload.user_id)


@app.post("/api/sync/claim", dependencies=[Depends(require_api_key)])
async def claim_pairing_code(payload: PairingClaimRequest):
    user_id = get_pairing_registry().claim(payload.code)
    if not user_id:
        raise HTTPException(status_code=404, detail="Code not found or expired. Codes are valid for 10 minutes.")
    return {"user_id": user_id}


@app.get("/api/sync/status", dependencies=[Depends(require_api_key)])
async def sync_status(user_id: str = Query("default")):
    """How many other live connections (other tabs/devices) are currently
    subscribed for this user_id — lets the UI show an 'N devices online' hint."""
    return {"connected_devices": get_sync_hub().device_count(user_id)}


@app.websocket("/ws/sync/{user_id}")
async def sync_websocket(websocket: WebSocket, user_id: str):
    """Live push channel: every other device sharing this `user_id` gets a small
    JSON nudge — {"event": "message_added"|"settings_updated"|"memory_updated"|
    "conversation_updated", "data": {...}} — whenever something changes, so
    open apps can refetch just that slice of state instead of polling."""
    hub = get_sync_hub()
    await hub.connect(user_id, websocket)
    try:
        while True:
            # We don't expect client -> server traffic on this channel, but
            # draining it keeps the socket alive and lets us detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        await hub.disconnect(user_id, websocket)


# ---------------- Conversations ----------------
def derive_title(message: str) -> str:
    """Turn a raw first message into a clean, short conversation title."""
    text = re.sub(r"\s+", " ", message).strip()
    text = re.sub(r"[`*_#>\[\]]", "", text)
    if len(text) <= 60:
        return text or "New conversation"
    cut = text[:60]
    last_space = cut.rfind(" ")
    if last_space > 30:
        cut = cut[:last_space]
    return cut.strip() + "…"


@app.post("/api/conversations", dependencies=[Depends(require_api_key)])
async def create_conversation(payload: NewConversationRequest):
    store = get_store()
    conv_id = await store.create_conversation(payload.user_id, payload.title)
    return {"conversation_id": conv_id}


@app.get("/api/conversations", dependencies=[Depends(require_api_key)])
async def list_conversations(user_id: str = Query("default")):
    store = get_store()
    return await store.list_conversations(user_id)


@app.get("/api/conversations/search", dependencies=[Depends(require_api_key)])
async def search_conversations(user_id: str = Query("default"), q: str = Query(..., min_length=1)):
    store = get_store()
    return await store.search_conversations(user_id, q)


@app.get("/api/conversations/{conversation_id}/messages", dependencies=[Depends(require_api_key)])
async def get_conversation_messages(conversation_id: str):
    store = get_store()
    return await store.get_messages(conversation_id)


@app.patch("/api/conversations/{conversation_id}", dependencies=[Depends(require_api_key)])
async def rename_conversation(conversation_id: str, payload: RenameConversationRequest):
    store = get_store()
    conv = await store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await store.rename_conversation(conversation_id, payload.title)
    await get_sync_hub().publish(conv["user_id"], "conversation_updated", {"conversation_id": conversation_id})
    return {"ok": True}


@app.delete("/api/conversations/{conversation_id}", dependencies=[Depends(require_api_key)])
async def delete_conversation(conversation_id: str):
    store = get_store()
    conv = await store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await store.delete_conversation(conversation_id)
    await get_sync_hub().publish(conv["user_id"], "conversation_deleted", {"conversation_id": conversation_id})
    return {"ok": True}


@app.post("/api/conversations/{conversation_id}/pin", dependencies=[Depends(require_api_key)])
async def pin_conversation(conversation_id: str, pinned: bool = Query(True)):
    store = get_store()
    conv = await store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await store.set_pinned(conversation_id, pinned)
    await get_sync_hub().publish(conv["user_id"], "conversation_updated", {"conversation_id": conversation_id})
    return {"ok": True}


# ---------------- Usage analytics ----------------
@app.get("/api/usage", dependencies=[Depends(require_api_key)])
async def get_usage(user_id: str = Query("default"), days: int = Query(30, ge=1, le=365)):
    store = get_store()
    return await store.get_usage_summary(user_id, days)


# ---------------- Persistent memory (Mira-style "what I remember about you") ----------------
@app.get("/api/memories", dependencies=[Depends(require_api_key)])
async def get_memories(user_id: str = Query("default"), q: Optional[str] = Query(None)):
    """List a user's remembered facts. Pass `q` for hybrid search (keyword +
    optional semantic, see memory/embeddings.py) instead of the full list —
    powers the CLI's `meiko memory search` and the Settings memory search box."""
    store = get_store()
    if q:
        return await store.search_memories(user_id, q)
    return await store.list_memories_full(user_id)


@app.post("/api/memories", dependencies=[Depends(require_api_key)])
async def add_memory(payload: MemoryCreateRequest):
    """Manually add a memory fact (the agent also does this itself via the
    `remember` tool mid-conversation) — powers `meiko memory add` in the CLI."""
    store = get_store()
    memory_id = await store.add_memory(payload.user_id, payload.fact)
    await get_sync_hub().publish(payload.user_id, "memory_updated")
    return {"id": memory_id}


@app.delete("/api/memories/{memory_id}", dependencies=[Depends(require_api_key)])
async def delete_memory(memory_id: str):
    store = get_store()
    memory = await store.get_memory(memory_id)
    await store.delete_memory(memory_id)
    if memory:
        await get_sync_hub().publish(memory["user_id"], "memory_updated")
    return {"ok": True}


@app.delete("/api/memories", dependencies=[Depends(require_api_key)])
async def clear_memories(user_id: str = Query("default")):
    store = get_store()
    await store.clear_memories(user_id)
    await get_sync_hub().publish(user_id, "memory_updated")
    return {"ok": True}


# ---------------- Connectors / Plugins ----------------
@app.get("/api/connectors", dependencies=[Depends(require_api_key)])
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


@app.post("/api/connectors", dependencies=[Depends(require_api_key)])
async def register_connector(payload: ConnectorManifestRequest):
    manager = get_connector_manager()
    manifest = manager.register_manifest(payload.manifest)
    return {"ok": True, "id": manifest.id}


@app.post("/api/connectors/{connector_id}/toggle", dependencies=[Depends(require_api_key)])
async def toggle_connector(connector_id: str, payload: ConnectorToggleRequest):
    manager = get_connector_manager()
    manager.set_enabled(connector_id, payload.enabled)
    return {"ok": True}


# ---------------- Upload / Download ----------------
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@app.post("/api/upload", dependencies=[Depends(require_api_key), Depends(enforce_general_rate_limit)])
async def upload_file(session_id: str = Query(...), file: UploadFile = File(...)):
    root = Path(settings.DATA_DIR) / "workspaces" / session_id / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name  # strip any path components
    dest = root / safe_name
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")
    dest.write_bytes(content)

    mime, _ = mimetypes.guess_type(safe_name)
    result: dict[str, str] = {"path": f"uploads/{safe_name}", "mime": mime or "application/octet-stream"}
    if mime and mime.startswith("image/"):
        b64 = base64.b64encode(content).decode()
        result["data_url"] = f"data:{mime};base64,{b64}"
    return result


@app.get("/api/workspace/{session_id}/files", dependencies=[Depends(require_api_key)])
async def list_workspace_files(session_id: str):
    """List every file Meiko has generated in a session's sandboxed workspace
    and exports folder — powers the web app's Artifacts panel (inspired by
    Open Design's artifact tree: every generated file, not just the last
    one, stays visible and downloadable alongside the chat)."""
    safe_session = Path(session_id).name
    roots = [
        ("workspace", Path(settings.DATA_DIR) / "workspaces" / safe_session),
        ("exports", Path(settings.DATA_DIR) / "exports" / safe_session),
    ]
    files: list[dict] = []
    for kind, root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(root)
            except ValueError:
                continue
            stat = p.stat()
            files.append({
                "name": str(rel),
                "kind": kind,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "download_url": f"/api/download/{safe_session}/{p.name}",
            })
    files.sort(key=lambda f: f["modified_at"], reverse=True)
    return files


@app.get("/api/download/{session_id}/{filename}", dependencies=[Depends(require_api_key)])
async def download_file(session_id: str, filename: str):
    safe_name = Path(filename).name  # prevent path traversal
    safe_session = Path(session_id).name
    candidates = [
        Path(settings.DATA_DIR) / "exports" / safe_session / safe_name,
        Path(settings.DATA_DIR) / "workspaces" / safe_session / safe_name,
        Path(settings.DATA_DIR) / "workspaces" / safe_session / "images" / safe_name,
    ]
    for path in candidates:
        if path.exists():
            return FileResponse(str(path), filename=safe_name)
    raise HTTPException(status_code=404, detail="File not found")


# ---------------- Chat (SSE streaming) ----------------
@app.post("/api/chat/stream", dependencies=[Depends(require_api_key), Depends(enforce_chat_rate_limit)])
async def chat_stream(payload: ChatRequest):
    store = get_store()
    session_id = payload.session_id or payload.conversation_id or str(uuid.uuid4())

    conversation_id = payload.conversation_id
    is_new_conversation = not conversation_id
    if is_new_conversation:
        conversation_id = await store.create_conversation(payload.user_id, title=derive_title(payload.message))

    user_settings = await store.get_user_settings(payload.user_id)
    provider_id = payload.provider or user_settings.get("provider") or settings.DEFAULT_PROVIDER
    model = payload.model or user_settings.get("model") or None
    api_keys = user_settings.get("api_keys", {})
    api_key_override = api_keys.get(provider_id)

    persona_text_parts = []
    if payload.persona_id:
        persona_obj = get_persona(payload.persona_id)
        if persona_obj.system_suffix:
            persona_text_parts.append(persona_obj.system_suffix)
    if payload.persona:
        persona_text_parts.append(payload.persona)
    elif user_settings.get("persona"):
        persona_text_parts.append(user_settings["persona"])
    effective_ui_language = payload.ui_language or user_settings.get("ui_language")
    if effective_ui_language and effective_ui_language.lower() not in ("en", "en-us", "en-gb", ""):
        persona_text_parts.append(
            f"Always reply in the following language/locale unless the user explicitly asks for another "
            f"language: {effective_ui_language}. Translate technical terms naturally, keep code blocks and "
            f"identifiers unchanged."
        )
    persona = "\n\n".join(persona_text_parts) or None

    history_rows = await store.get_messages(conversation_id, limit=40)
    history: list[ChatMessage] = []
    for row in history_rows:
        if row["role"] in ("user", "assistant"):
            history.append(ChatMessage(role=row["role"], content=row["content"]))

    await store.add_message(conversation_id, "user", payload.message)
    await get_sync_hub().publish(payload.user_id, "message_added", {"conversation_id": conversation_id, "role": "user"})

    image_urls = payload.image_paths or None

    agent = MeikoAgent(
        settings,
        provider_id=provider_id,
        model=model,
        api_key_override=api_key_override,
        persona_extra=persona,
        mode_id=payload.mode,
        connector_secrets=api_keys,
        provider_api_keys=api_keys,
        enable_fallback=payload.enable_fallback,
    )

    async def event_generator():
        final_text = ""
        run_stats = {"steps": 0, "tool_calls": 0, "elapsed_seconds": 0.0}
        had_error = False
        try:
            if is_new_conversation:
                yield AgentEvent(type="conversation_created", data={"conversation_id": conversation_id, "title": derive_title(payload.message)}).to_sse()
                await get_sync_hub().publish(
                    payload.user_id, "conversation_created",
                    {"conversation_id": conversation_id, "title": derive_title(payload.message)},
                )
            async for event in agent.run(session_id, payload.user_id, history, payload.message, image_urls=image_urls):
                if event.type == "final":
                    final_text = event.data.get("text", "")
                    run_stats = event.data.get("stats", run_stats)
                if event.type == "error":
                    had_error = True
                yield event.to_sse()
        except Exception as e:  # noqa: BLE001
            had_error = True
            logger.exception("chat_stream failure conversation_id=%s", conversation_id)
            yield AgentEvent(type="error", data={"message": f"Unexpected server error: {e}"}).to_sse()
        finally:
            if final_text:
                await store.add_message(conversation_id, "assistant", final_text)
                await store.touch_conversation(conversation_id)
                await get_sync_hub().publish(
                    payload.user_id, "message_added",
                    {"conversation_id": conversation_id, "role": "assistant"},
                )
            try:
                await store.log_usage(
                    payload.user_id, provider_id, payload.mode,
                    tool_calls=run_stats.get("tool_calls", 0),
                    steps=run_stats.get("steps", 0),
                    elapsed_seconds=run_stats.get("elapsed_seconds", 0.0),
                    error=had_error,
                )
            except Exception:  # noqa: BLE001
                logger.warning("failed to log usage event")

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
