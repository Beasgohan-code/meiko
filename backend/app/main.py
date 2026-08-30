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
  - GET  /api/preview/{session_id}/{file_path} -> inline-render a generated file
    (e.g. index.html) for the vibe-coding mode's live iframe preview
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

import asyncio
import base64
import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
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
    RunStartRequest,
    SettingsUpdateRequest,
    SkillCreateRequest,
    ToolGenerateRequest,
)
from .core.config import get_settings
from .core.logging import get_logger, new_request_id, request_id_ctx, setup_logging
from .core.modes import list_modes
from .core.personas import get_persona, list_personas
from .tools.skills import SkillValidationError, delete_skill, discover_skills, get_skill, save_skill
from .core.security import (
    enforce_chat_rate_limit,
    enforce_general_rate_limit,
    require_api_key,
    require_api_key_header_or_query,
)
from .core.sync import get_pairing_registry, get_sync_hub
from .core import auth as auth_core
from .core.run_console import get_run_manager
from .harness.agent import AgentEvent, MeikoAgent
from .memory.store import get_store
from .plugins.manager import get_connector_manager
from .providers.base import ChatMessage
from .providers.registry import list_provider_meta
from .providers.model_catalog import list_models
from .tools.custom_tools import (
    CustomToolValidationError,
    delete_custom_tool,
    list_custom_tool_specs,
    save_custom_tool,
    validate_spec,
)

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


# ---------------- Auth (GitHub OAuth + JWT sessions) ----------------
_oauth_states: dict[str, dict] = {}  # state -> {"ts": float, "client_redirect": Optional[str]}


def _client_redirect_allowed(url: str) -> bool:
    """Small allowlist so `client_redirect` can't be used as an open
    redirect: the configured web frontend URL, localhost (dev), or the
    native Android app's own custom URI scheme (registered in its
    manifest — see android/.../MainActivity.kt)."""
    settings = get_settings()
    allowed_prefixes = (
        settings.OAUTH_FRONTEND_REDIRECT_URL,
        "http://localhost",
        "http://127.0.0.1",
        "meiko://auth",
    )
    return any(url.startswith(p) for p in allowed_prefixes)


@app.get("/api/auth/config")
async def auth_config():
    """Lets the UI know whether to show the 'Sign in with GitHub' button at
    all — Meiko works fully accountless if this isn't configured."""
    return {"github_enabled": auth_core.github_oauth_configured()}


@app.get("/api/auth/github/login")
async def github_login(request: Request, client_redirect: Optional[str] = Query(default=None)):
    if not auth_core.github_oauth_configured():
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured on this server")
    if client_redirect and not _client_redirect_allowed(client_redirect):
        raise HTTPException(status_code=400, detail="client_redirect is not on the allowlist")
    state = uuid.uuid4().hex
    now = time.time()
    _oauth_states[state] = {"ts": now, "client_redirect": client_redirect}
    # sweep stale states (10 min TTL) so this dict can't grow unbounded
    for k in [k for k, v in _oauth_states.items() if now - v["ts"] > 600]:
        _oauth_states.pop(k, None)
    # Callback must exactly match a URL registered on the GitHub OAuth App
    # (same host/scheme this login request came in on).
    callback_url = str(request.url_for("github_callback"))
    return RedirectResponse(auth_core.build_github_authorize_url(callback_url, state))


@app.get("/api/auth/github/callback")
async def github_callback(request: Request, code: str = Query(...), state: str = Query(...)):
    if not auth_core.github_oauth_configured():
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured on this server")
    state_entry = _oauth_states.pop(state, None)
    if not state_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    redirect_uri = str(request.url).split("?")[0]
    profile = await auth_core.exchange_github_code(code, redirect_uri)
    store = get_store()
    user = await store.get_or_create_oauth_user(
        provider="github",
        provider_uid=profile["github_id"],
        username=profile["username"],
        name=profile.get("name"),
        email=profile.get("email"),
        avatar_url=profile.get("avatar_url"),
    )
    token = auth_core.issue_session_token(user["id"], user["username"])
    frontend_url = state_entry.get("client_redirect") or settings.OAUTH_FRONTEND_REDIRECT_URL
    # Token goes in the URL *fragment* (#...), which browsers never send to
    # a server, so it can't end up in this server's or any proxy's access
    # logs the way a query string would. Android's custom-scheme redirect
    # (meiko://auth#token=...) is handled the same way by its WebView.
    return RedirectResponse(f"{frontend_url}#token={token}")


@app.get("/api/auth/me")
async def auth_me(session=Depends(auth_core.require_user)):
    store = get_store()
    user = await store.get_user(session["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user["id"],
        "username": user["username"],
        "name": user.get("name"),
        "email": user.get("email"),
        "avatar_url": user.get("avatar_url"),
    }


@app.post("/api/auth/logout")
async def auth_logout():
    # Sessions are stateless JWTs; logout is a client-side token discard.
    # This endpoint exists for a symmetric client flow and as a hook point
    # if server-side token revocation (e.g. a deny-list) is added later.
    return {"status": "ok"}


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


@app.post("/api/skills", dependencies=[Depends(require_api_key)])
async def create_skill(payload: SkillCreateRequest):
    """Lets the web/Android 'add a skill' UI write a real SKILL.md on disk
    (same format the built-in skills ship in) without touching a
    filesystem directly — the agent's list_skills/use_skill tools pick it
    up immediately on the next request, no restart needed."""
    try:
        skill = save_skill(
            name=payload.name,
            description=payload.description,
            triggers=payload.triggers,
            body=payload.body,
            skill_id=payload.skill_id,
        )
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": skill.id, "name": skill.name, "description": skill.description, "triggers": skill.triggers, "body": skill.body}


@app.put("/api/skills/{skill_id}", dependencies=[Depends(require_api_key)])
async def update_skill(skill_id: str, payload: SkillCreateRequest):
    if get_skill(skill_id) is None:
        raise HTTPException(status_code=404, detail=f"No skill named '{skill_id}'")
    try:
        skill = save_skill(
            name=payload.name,
            description=payload.description,
            triggers=payload.triggers,
            body=payload.body,
            skill_id=skill_id,
        )
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": skill.id, "name": skill.name, "description": skill.description, "triggers": skill.triggers, "body": skill.body}


@app.delete("/api/skills/{skill_id}", dependencies=[Depends(require_api_key)])
async def delete_skill_route(skill_id: str):
    try:
        deleted = delete_skill(skill_id)
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No skill named '{skill_id}'")
    return {"status": "deleted", "id": skill_id}


# ---------------- Dev Console (arena.ai/menus.ai-style live command runner) ----------------
@app.post("/api/console/run", dependencies=[Depends(require_api_key)])
async def console_run(payload: RunStartRequest):
    """Starts a bash or python run in the caller's sandboxed session
    workspace and returns immediately with a run_id — the run keeps
    executing and streaming output into an in-memory buffer that
    /api/console/{run_id}/output (poll) or /ws/console/{run_id} (push)
    can read from, so a UI can show a real live terminal instead of
    waiting for one final blob like the agent's own run_bash/run_python
    tools do."""
    manager = get_run_manager()
    try:
        run = await manager.start(
            payload.session_id, payload.command, kind=payload.kind, timeout_seconds=payload.timeout_seconds
        )
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return run.to_summary()


@app.get("/api/console/{run_id}/output", dependencies=[Depends(require_api_key)])
async def console_output(
    run_id: str,
    since: int = Query(0, ge=0),
    wait_for: Optional[str] = Query(default=None, pattern="^(exit|log)$"),
    wait_pattern: Optional[str] = Query(default=None),
    wait_timeout: float = Query(default=20.0, ge=0.1, le=120.0),
):
    """Poll for new output since a byte cursor — same 'give me what's new'
    shape as this project's own get_process_output sandbox tool, including
    optional short blocking waits (wait_for=exit|log) so a UI doesn't need
    to tight-poll for a fast command."""
    manager = get_run_manager()
    try:
        return await manager.get_output(
            run_id, since=since, wait_for=wait_for, wait_pattern=wait_pattern, wait_timeout=wait_timeout
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown run_id")


@app.get("/api/console/{session_id}/runs", dependencies=[Depends(require_api_key)])
async def console_list_runs(session_id: str):
    manager = get_run_manager()
    return [r.to_summary() for r in manager.list_for_session(session_id)]


@app.post("/api/console/{run_id}/stop", dependencies=[Depends(require_api_key)])
async def console_stop(run_id: str):
    manager = get_run_manager()
    stopped = await manager.stop(run_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Run not found or already finished")
    return {"status": "stopped", "run_id": run_id}


@app.websocket("/ws/console/{run_id}")
async def console_websocket(websocket: WebSocket, run_id: str):
    """Live push channel for a single run: sends every new output chunk the
    instant it's produced, for a real-time terminal feel (menus.ai/arena.ai
    style), then a final {"event":"exit", ...} message when the process
    ends. Falls back gracefully to the polling endpoint above if a client
    can't use WebSockets."""
    manager = get_run_manager()
    run = manager.get(run_id)
    if not run:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    # Replay everything buffered so far, then subscribe for new chunks.
    existing_text, cursor = run.slice_since(0)
    if existing_text:
        await websocket.send_json({"event": "output", "text": existing_text, "cursor": cursor})
    if run.status != "running":
        await websocket.send_json({"event": "exit", **run.to_summary()})
        await websocket.close()
        return

    run.subscribers.add(queue)
    try:
        while True:
            chunk = await queue.get()
            if chunk is None:  # sentinel: process finished
                await websocket.send_json({"event": "exit", **run.to_summary()})
                break
            text, cursor = run.slice_since(run.total_len() - len(chunk))
            await websocket.send_json({"event": "output", "text": chunk.decode(errors="replace"), "cursor": run.total_len()})
    except WebSocketDisconnect:
        pass
    finally:
        run.subscribers.discard(queue)


# ---------------- Tools Generator (dev-mode: describe a tool, get a real one) ----------------
@app.post("/api/tools/generate", dependencies=[Depends(require_api_key)])
async def generate_tool(payload: ToolGenerateRequest):
    """Turns a plain-language tool description into a real, callable Tool
    the agent can invoke on its very next turn — no server restart, no
    code deploy. See tools/custom_tools.py for the two supported shapes
    (HTTP-templated, or a short sandboxed Python body)."""
    try:
        spec = validate_spec(
            name=payload.name,
            description=payload.description,
            parameters=payload.parameters,
            kind=payload.kind,
            http_method=payload.http_method or "GET",
            http_url_template=payload.http_url_template,
            http_headers=payload.http_headers,
            python_body=payload.python_body,
        )
    except CustomToolValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_custom_tool(spec)
    return spec.to_dict()


@app.get("/api/tools/generated", dependencies=[Depends(require_api_key)])
async def list_generated_tools():
    return [s.to_dict() for s in list_custom_tool_specs()]


@app.delete("/api/tools/generated/{name}", dependencies=[Depends(require_api_key)])
async def delete_generated_tool(name: str):
    try:
        deleted = delete_custom_tool(name)
    except CustomToolValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No custom tool named '{name}'")
    return {"status": "deleted", "name": name}


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
        custom_base_url=payload.custom_base_url,
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
            entry = {
                "name": str(rel),
                "kind": kind,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "download_url": f"/api/download/{safe_session}/{p.name}",
            }
            ext = p.suffix.lower()
            if kind == "workspace" and ext in (".html", ".htm"):
                # Live-rendered preview — the vibe-coding payoff (real page in an iframe).
                entry["preview_url"] = f"/api/preview/{safe_session}/{rel.as_posix()}"
                entry["preview_kind"] = "render"
            elif kind == "workspace" and ext in (
                ".js", ".jsx", ".ts", ".tsx", ".css", ".json", ".md", ".txt", ".py", ".yaml", ".yml"
            ):
                # Generalized code preview — a shareable, syntax-highlighted
                # read-only page for any generated source file, not just
                # HTML (extends the Vibe Coding live-preview feature to
                # every artifact Meiko writes).
                entry["preview_url"] = f"/api/preview-page/{safe_session}/{rel.as_posix()}"
                entry["preview_kind"] = "code"
            files.append(entry)
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


@app.get("/api/preview/{session_id}/{file_path:path}", dependencies=[Depends(require_api_key_header_or_query)])
async def preview_file(session_id: str, file_path: str):
    """Serve a generated workspace file inline (not as an attachment) with a
    real content-type, so it can be dropped straight into an <iframe> for a
    live preview -- the core "vibe coding" payoff: write an index.html with
    write_file and see it rendered instantly, bolt.new/v0-style, without
    downloading anything. Accepts nested paths (e.g. 'src/index.html')."""
    safe_session = Path(session_id).name
    root = (Path(settings.DATA_DIR) / "workspaces" / safe_session).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(target.name)
    return FileResponse(str(target), media_type=mime or "text/plain")


_CODE_PREVIEW_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background: #0d0d12; color: #e7e7ee; }}
  header {{ display: flex; align-items: center; gap: 10px; padding: 10px 16px; background: #16161f; border-bottom: 1px solid #26263a; position: sticky; top: 0; }}
  header .name {{ font-weight: 600; font-size: 13px; }}
  header .badge {{ font-size: 11px; padding: 2px 8px; border-radius: 999px; background: #7c5cff33; color: #b6a6ff; }}
  main {{ padding: 0; }}
  pre {{ margin: 0; padding: 20px 24px 60px; overflow-x: auto; font-size: 13px; line-height: 1.6; white-space: pre; }}
  .line-no {{ display: inline-block; width: 3.5em; color: #55556b; user-select: none; text-align: right; margin-right: 1.2em; }}
</style></head>
<body>
<header><span class="name">{title}</span><span class="badge">Meiko live preview</span></header>
<main><pre>{content}</pre></main>
</body></html>"""


@app.get("/api/preview-page/{session_id}/{file_path:path}", dependencies=[Depends(require_api_key_header_or_query)])
async def preview_page(session_id: str, file_path: str):
    """Shareable, read-only rendered preview for any generated source file
    (JS/TS/CSS/JSON/Markdown/Python/YAML/...), generalizing the Vibe-Coding
    live-preview beyond just HTML: this is what a 'preview link' opens for
    a non-HTML artifact — a real page with line numbers, not a raw-text
    download prompt. HTML files still use /api/preview for a true rendered
    iframe; this route is for source files meant to be *read*, not run."""
    import html as html_module

    safe_session = Path(session_id).name
    root = (Path(settings.DATA_DIR) / "workspaces" / safe_session).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raise HTTPException(status_code=404, detail="File not found")

    lines = text.splitlines() or [""]
    numbered = "\n".join(
        f'<span class="line-no">{i + 1}</span>{html_module.escape(line)}' for i, line in enumerate(lines)
    )
    page = _CODE_PREVIEW_TEMPLATE.format(title=html_module.escape(target.name), content=numbered)
    return HTMLResponse(page)


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

    base_url_override = user_settings.get("custom_base_url") if provider_id == "custom" else None

    agent = MeikoAgent(
        settings,
        provider_id=provider_id,
        model=model,
        api_key_override=api_key_override,
        base_url_override=base_url_override,
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
