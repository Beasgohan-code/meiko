"""
Meiko Telegram Bot — professional, feature-complete client for the Meiko agent harness.

Uses modern python-telegram-bot v21 (Bot API 7+) features:
  - Inline keyboards for mode/persona/provider/connector switching
  - Live-edited streaming responses with plan checklists, tool traces, and citations
  - A full command menu registered via set_my_commands (shows in Telegram's "/" picker)
  - Photo & document upload support (forwarded into Meiko's session workspace)
  - Web App / mini-app launch button (if MEIKO_WEBAPP_URL is configured)
  - Message reactions (Bot API 7.0+) — reacts on the user's message once Meiko finishes
  - /stop to cancel an in-flight generation
  - Conversation history browser (list/resume/rename/delete) via inline keyboards
  - /github to store a GitHub PAT for read+write repo tools
  - /usage for per-user usage analytics
  - Optional allow-list access control (TELEGRAM_ALLOWED_USER_IDS)
  - MarkdownV2-safe rendering with graceful fallback to plain text
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReactionTypeEmoji,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import config
from .meiko_client import (
    clear_memories,
    delete_conversation,
    download_url,
    fetch_connectors,
    fetch_models,
    fetch_modes,
    fetch_personas,
    fetch_providers,
    fetch_skills,
    get_conversation_messages,
    get_memories,
    get_usage,
    list_conversations,
    rename_conversation,
    search_conversations,
    set_user_settings,
    stream_chat,
    toggle_connector,
    upload_file,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("meiko-bot")

MODE_EMOJI = {
    "chat": "💬", "research": "🔎", "code": "💻", "autonomous": "🤖", "creative": "🎨",
}

# in-flight generation tasks per chat, so /stop can cancel them
_ACTIVE_TASKS: dict[int, asyncio.Task] = {}


def _chat_state(context: ContextTypes.DEFAULT_TYPE) -> dict:
    context.user_data.setdefault("mode", "autonomous")
    context.user_data.setdefault("persona_id", "default")
    context.user_data.setdefault("conversation_id", None)
    context.user_data.setdefault("session_id", str(uuid.uuid4()))
    context.user_data.setdefault("provider", None)
    context.user_data.setdefault("model", None)
    context.user_data.setdefault("ui_language", None)
    return context.user_data


LANGUAGE_CHOICES = [
    ("en", "🇬🇧 English"), ("es", "🇪🇸 Español"), ("fr", "🇫🇷 Français"), ("de", "🇩🇪 Deutsch"),
    ("hi", "🇮🇳 हिन्दी"), ("pt", "🇵🇹 Português"), ("ar", "🇸🇦 العربية"), ("ja", "🇯🇵 日本語"),
    ("zh", "🇨🇳 中文"), ("ru", "🇷🇺 Русский"), ("ko", "🇰🇷 한국어"), ("id", "🇮🇩 Bahasa Indonesia"),
]


def _user_id(update: Update) -> str:
    return f"tg-{update.effective_user.id}"


def _is_allowed(update: Update) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    return update.effective_user.id in config.ALLOWED_USER_IDS


async def _guard(update: Update) -> bool:
    if not _is_allowed(update):
        if update.message:
            await update.message.reply_text("🚫 This Meiko bot instance is private. Ask the owner to add your Telegram user id.")
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _chat_state(context)
    buttons = [
        [
            InlineKeyboardButton("🧭 Agent Mode", callback_data="menu:mode"),
            InlineKeyboardButton("🎭 Persona", callback_data="menu:persona"),
        ],
        [
            InlineKeyboardButton("🔑 Providers", callback_data="menu:providers"),
            InlineKeyboardButton("🧬 Model", callback_data="menu:model"),
        ],
        [
            InlineKeyboardButton("🧩 Connectors", callback_data="menu:connectors"),
            InlineKeyboardButton("🧠 Skills", callback_data="menu:skills"),
        ],
        [
            InlineKeyboardButton("🗂 History", callback_data="menu:history"),
            InlineKeyboardButton("🌐 Language", callback_data="menu:lang"),
        ],
    ]
    if config.WEBAPP_URL:
        buttons.append([InlineKeyboardButton("🌐 Open Meiko Web App", web_app=WebAppInfo(url=config.WEBAPP_URL))])

    await update.message.reply_text(
        "👋 *Hey, I'm Meiko!*\n\n"
        "Your open, pluggable autonomous AI agent — pick from 20+ free NVIDIA models (DeepSeek, Kimi, GLM, "
        "Qwen, Llama and more), plus Gemini/Groq/OpenRouter. I can research the web, write & run code and shell "
        "commands, generate images, remember things about you long-term, use Skills for specialized playbooks, "
        "and connect to GitHub (read *and* write), Wikipedia, Reddit, Hacker News, and weather.\n\n"
        "Just send me a message to get started, or use the menu below.\n\n"
        "*Commands:* /mode /persona /providers /model /lang /memory /connectors /skills /github /history "
        "/rename /usage /new /stop /help",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cmd_imagine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /imagine a neon cyberpunk city at sunset, cinematic lighting")
        return
    prompt = " ".join(context.args)
    await on_message_with_text(update, context, f"Generate an image of: {prompt}")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    state = _chat_state(context)
    state["conversation_id"] = None
    state["session_id"] = str(uuid.uuid4())
    await update.message.reply_text("🆕 Started a fresh conversation. What's on your mind?")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    chat_id = update.effective_chat.id
    task = _ACTIVE_TASKS.get(chat_id)
    if task and not task.done():
        task.cancel()
        await update.message.reply_text("⏹ Stopped.")
    else:
        await update.message.reply_text("Nothing is currently running.")


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    modes = await fetch_modes()
    buttons = [
        [InlineKeyboardButton(f"{MODE_EMOJI.get(m['id'], '✨')} {m['name']} — {m['description'][:40]}", callback_data=f"mode:{m['id']}")]
        for m in modes
    ]
    await update.message.reply_text("Pick an agent mode:", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_persona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    personas = await fetch_personas()
    buttons = [
        [InlineKeyboardButton(f"{p['name']} — {p['tagline'][:40]}", callback_data=f"persona:{p['id']}")]
        for p in personas
    ]
    await update.message.reply_text("Pick a persona:", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_providers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    providers = await fetch_providers()
    buttons = [[InlineKeyboardButton(f"{'🆓' if p.get('free_tier') else '💳'} {p['display_name']}", callback_data=f"provider:{p['id']}")] for p in providers]
    await update.message.reply_text(
        "Pick your default model provider (add API keys in the web app's Settings for full control):",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


MODEL_TAG_EMOJI = {"flagship": "🏆", "fast": "⚡", "coding": "💻", "vision": "👁", "default": "⭐"}


def _model_button_label(m: dict) -> str:
    tag = MODEL_TAG_EMOJI.get(m.get("tag", ""), "")
    reasoning = "🧠" if m.get("reasoning") else ""
    vision = "👁" if m.get("vision") and m.get("tag") != "vision" else ""
    ctx = f" · {m['context_window']}" if m.get("context_window") else ""
    return f"{tag}{reasoning}{vision} {m['display_name']}{ctx}".strip()


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    state = _chat_state(context)
    provider_id = state.get("provider") or "nvidia"
    models = await fetch_models(provider_id)
    if not models:
        await update.message.reply_text(f"No curated models found for provider '{provider_id}'.")
        return
    buttons = [[InlineKeyboardButton(_model_button_label(m), callback_data=f"model:{m['id']}")] for m in models[:24]]
    await update.message.reply_text(
        f"🧬 Pick a model for *{provider_id}* (🏆 flagship · ⚡ fast · 💻 coding · 👁 vision · 🧠 reasoning):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"lang:{code}") for code, label in LANGUAGE_CHOICES[i:i + 2]]
        for i in range(0, len(LANGUAGE_CHOICES), 2)
    ]
    await update.message.reply_text("🌐 Choose the language Meiko should reply in:", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    user_id = _user_id(update)
    memories = await get_memories(user_id)
    if not memories:
        await update.message.reply_text(
            "🧠 I don't have any long-term memories about you yet — as we chat, I'll save durable facts "
            "(preferences, ongoing projects, etc.) here automatically."
        )
        return
    lines = ["*What I remember about you:*"]
    for m in memories[:30]:
        lines.append(f"• {m['fact']}")
    buttons = [[InlineKeyboardButton("🗑 Forget everything", callback_data="mem_clear")]]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_connectors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    connectors = await fetch_connectors()
    buttons = [
        [InlineKeyboardButton(f"{'✅' if c['enabled'] else '⬜️'} {c['name']}", callback_data=f"connector:{c['id']}")]
        for c in connectors
    ]
    await update.message.reply_text("Tap to toggle a connector on/off:", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    skills = await fetch_skills()
    if not skills:
        await update.message.reply_text("No skills installed yet.")
        return
    lines = ["*Available Skills* — Meiko loads these automatically when relevant:\n"]
    for s in skills:
        lines.append(f"🧠 *{s['name']}*\n{s['description']}")
    await update.message.reply_text("\n\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_github(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    args = context.args
    user_id = _user_id(update)
    if not args:
        await update.message.reply_text(
            "To let Meiko read *and write* to your GitHub repos (commit files, open PRs, create issues), "
            "send:\n`/github ghp_your_token_here`\n\n"
            "Create one with repo scope: https://github.com/settings/tokens/new?scopes=repo",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    token = args[0].strip()
    await set_user_settings(user_id, api_keys={"github": token})
    await update.message.reply_text("✅ GitHub token saved. I can now read and write to your repos when you ask.")


async def cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    user_id = _user_id(update)
    data = await get_usage(user_id, days=30)
    totals = data.get("totals", {})
    lines = [
        "*Your Meiko usage (last 30 days)*",
        f"Requests: {totals.get('total', 0)}",
        f"Tool calls: {totals.get('tool_calls', 0) or 0}",
        f"Errors: {totals.get('errors', 0) or 0}",
    ]
    for row in data.get("by_provider_mode", []):
        lines.append(f"  • {row['provider']}/{row['mode']}: {row['n']} runs, {row.get('tool_calls') or 0} tool calls")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if context.args:
        query = " ".join(context.args)
        await _send_history(update.message, _user_id(update), query=query)
    else:
        await _send_history(update.message, _user_id(update))


async def cmd_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    state = _chat_state(context)
    if not state.get("conversation_id"):
        await update.message.reply_text("No active conversation yet to rename — send a message first.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /rename New conversation title")
        return
    title = " ".join(context.args)
    await rename_conversation(state["conversation_id"], title)
    await update.message.reply_text(f"✅ Renamed to: {title}")


async def _send_history(message, user_id: str, query: str | None = None) -> None:
    convs = await search_conversations(user_id, query) if query else await list_conversations(user_id)
    if not convs:
        await message.reply_text("No conversations yet — just send me a message to start one!")
        return
    buttons = []
    for c in convs[:15]:
        title = (c.get("title") or "Untitled")[:40]
        pin = "📌 " if c.get("pinned") else ""
        buttons.append([
            InlineKeyboardButton(f"{pin}{title}", callback_data=f"conv_open:{c['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"conv_del:{c['id']}"),
        ])
    await message.reply_text("Your recent conversations:", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    state = _chat_state(context)
    user_id = _user_id(update)

    if data == "menu:mode":
        modes = await fetch_modes()
        buttons = [[InlineKeyboardButton(f"{MODE_EMOJI.get(m['id'], '✨')} {m['name']}", callback_data=f"mode:{m['id']}")] for m in modes]
        await query.edit_message_text("Pick an agent mode:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "menu:persona":
        personas = await fetch_personas()
        buttons = [[InlineKeyboardButton(p["name"], callback_data=f"persona:{p['id']}")] for p in personas]
        await query.edit_message_text("Pick a persona:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "menu:providers":
        providers = await fetch_providers()
        buttons = [[InlineKeyboardButton(f"{'🆓' if p.get('free_tier') else '💳'} {p['display_name']}", callback_data=f"provider:{p['id']}")] for p in providers]
        await query.edit_message_text("Pick your default model provider:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "menu:connectors":
        connectors = await fetch_connectors()
        buttons = [[InlineKeyboardButton(f"{'✅' if c['enabled'] else '⬜️'} {c['name']}", callback_data=f"connector:{c['id']}")] for c in connectors]
        await query.edit_message_text("Tap to toggle a connector on/off:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "menu:skills":
        skills = await fetch_skills()
        text = "\n\n".join(f"🧠 *{s['name']}*\n{s['description']}" for s in skills) or "No skills installed."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    elif data == "menu:history":
        await _send_history(query.message, user_id)
    elif data == "menu:model":
        provider_id = state.get("provider") or "nvidia"
        models = await fetch_models(provider_id)
        buttons = [[InlineKeyboardButton(_model_button_label(m), callback_data=f"model:{m['id']}")] for m in models[:24]]
        await query.edit_message_text(
            f"🧬 Pick a model for *{provider_id}*:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(buttons)
        )
    elif data == "menu:lang":
        buttons = [
            [InlineKeyboardButton(label, callback_data=f"lang:{code}") for code, label in LANGUAGE_CHOICES[i:i + 2]]
            for i in range(0, len(LANGUAGE_CHOICES), 2)
        ]
        await query.edit_message_text("🌐 Choose the language Meiko should reply in:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("mode:"):
        mode_id = data.split(":", 1)[1]
        state["mode"] = mode_id
        await query.edit_message_text(f"✅ Agent mode set to *{mode_id}*.", parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("persona:"):
        persona_id = data.split(":", 1)[1]
        state["persona_id"] = persona_id
        await query.edit_message_text(f"✅ Persona set to *{persona_id}*.", parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("provider:"):
        provider_id = data.split(":", 1)[1]
        state["provider"] = provider_id
        state["model"] = None
        await set_user_settings(user_id, provider=provider_id)
        await query.edit_message_text(
            f"✅ Default provider set to *{provider_id}*.\nUse /model to pick a specific model for it.",
            parse_mode=ParseMode.MARKDOWN,
        )
    elif data.startswith("model:"):
        model_id = data.split(":", 1)[1]
        state["model"] = model_id
        await set_user_settings(user_id, model=model_id)
        await query.edit_message_text(f"✅ Model set to `{model_id}`.", parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("lang:"):
        lang_code = data.split(":", 1)[1]
        state["ui_language"] = lang_code
        await set_user_settings(user_id, ui_language=lang_code)
        label = next((label for code, label in LANGUAGE_CHOICES if code == lang_code), lang_code)
        await query.edit_message_text(f"✅ I'll reply in {label} from now on.")
    elif data == "mem_clear":
        await clear_memories(user_id)
        await query.edit_message_text("🗑 Cleared everything I remembered about you.")
    elif data.startswith("connector:"):
        connector_id = data.split(":", 1)[1]
        connectors = await fetch_connectors()
        current = next((c for c in connectors if c["id"] == connector_id), None)
        new_state = not (current["enabled"] if current else False)
        await toggle_connector(connector_id, new_state)
        connectors = await fetch_connectors()
        buttons = [[InlineKeyboardButton(f"{'✅' if c['enabled'] else '⬜️'} {c['name']}", callback_data=f"connector:{c['id']}")] for c in connectors]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("conv_open:"):
        conv_id = data.split(":", 1)[1]
        state["conversation_id"] = conv_id
        state["session_id"] = conv_id
        rows = await get_conversation_messages(conv_id)
        preview = "\n".join(f"{'🧑' if r['role']=='user' else '🤖'} {r['content'][:120]}" for r in rows[-6:])
        await query.edit_message_text(f"📂 Resumed conversation.\n\n{preview or '(empty)'}")
    elif data.startswith("conv_del:"):
        conv_id = data.split(":", 1)[1]
        await delete_conversation(conv_id)
        if state.get("conversation_id") == conv_id:
            state["conversation_id"] = None
            state["session_id"] = str(uuid.uuid4())
        await query.edit_message_text("🗑 Conversation deleted.")


def _escape_md(text: str) -> str:
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


def _format_plan(tasks: list[dict]) -> str:
    if not tasks:
        return ""
    icon = {"done": "✅", "in_progress": "🔄", "pending": "⬜️"}
    lines = [f"{icon.get(t.get('status'), '⬜️')} {t.get('text', '')}" for t in tasks]
    return "*Plan:*\n" + "\n".join(lines)


def _format_citations(sources: list[dict]) -> str:
    if not sources:
        return ""
    lines = [f"🔗 {s['url']}" for s in sources[:6]]
    return "*Sources:*\n" + "\n".join(lines)


async def _run_chat_turn(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    state = _chat_state(context)
    user_id = _user_id(update)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    placeholder = await update.message.reply_text("💭 _Meiko is thinking…_", parse_mode=ParseMode.MARKDOWN)

    buffer = ""
    tool_lines: list[str] = []
    plan_text = ""
    citations_text = ""
    last_edit = 0.0
    final_text = ""
    new_conversation_id = None
    had_error = False
    generated_images: list[str] = []

    def compose() -> str:
        parts = []
        if plan_text:
            parts.append(plan_text)
        if tool_lines:
            parts.append("\n".join(tool_lines[-4:]))
        if buffer:
            parts.append(buffer)
        return "\n\n".join(parts) if parts else "💭 _thinking…_"

    try:
        async for event in stream_chat(
            user_id,
            text,
            mode=state["mode"],
            conversation_id=state["conversation_id"],
            session_id=state["session_id"],
            persona_id=state["persona_id"],
            provider=state.get("provider"),
            model=state.get("model"),
            ui_language=state.get("ui_language"),
        ):
            etype = event.get("type")
            if etype == "conversation_created":
                new_conversation_id = event.get("conversation_id")
            elif etype == "plan_update":
                plan_text = _format_plan(event.get("tasks", []))
                now = time.time()
                if now - last_edit > config.EDIT_THROTTLE_SECONDS:
                    await _safe_edit(placeholder, compose()[-3800:])
                    last_edit = now
            elif etype == "tool_call":
                tool_lines.append(f"🔧 using `{event.get('name')}`…")
                now = time.time()
                if now - last_edit > config.EDIT_THROTTLE_SECONDS:
                    await _safe_edit(placeholder, compose()[-3800:])
                    last_edit = now
            elif etype == "tool_result":
                if event.get("name") == "generate_image":
                    result = str(event.get("result", ""))
                    if result.startswith("images/"):
                        generated_images.append(result[len("images/"):])
            elif etype == "provider_switch":
                tool_lines.append(f"⚠️ switched provider: {event.get('from')} → {event.get('to')}")
            elif etype == "token":
                buffer += event.get("text", "")
                now = time.time()
                if now - last_edit > config.EDIT_THROTTLE_SECONDS:
                    await _safe_edit(placeholder, compose()[-3800:])
                    last_edit = now
            elif etype == "citations":
                citations_text = _format_citations(event.get("sources", []))
            elif etype == "final":
                final_text = event.get("text", buffer)
            elif etype == "error":
                had_error = True
                await _safe_edit(placeholder, f"⚠️ Error: {event.get('message')}")
            elif etype == "done":
                if not new_conversation_id:
                    new_conversation_id = event.get("conversation_id")

        if not had_error:
            display_final = final_text or buffer or "…"
            if citations_text:
                display_final = f"{display_final}\n\n{citations_text}"
            await _safe_edit(placeholder, display_final[:4000])
            for img_filename in generated_images:
                try:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=download_url(state["session_id"], img_filename),
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("failed to send generated image %s", img_filename)
            try:
                await context.bot.set_message_reaction(
                    chat_id=update.effective_chat.id,
                    message_id=update.message.message_id,
                    reaction=[ReactionTypeEmoji(emoji="👍")],
                )
            except Exception:  # noqa: BLE001 — reactions may be unsupported in some chats
                pass

        if new_conversation_id and not state["conversation_id"]:
            state["conversation_id"] = new_conversation_id

    except asyncio.CancelledError:
        await _safe_edit(placeholder, "⏹ Stopped.")
        raise
    except Exception as e:
        logger.exception("chat stream failed")
        await _safe_edit(placeholder, f"⚠️ Something went wrong talking to Meiko's backend: {e}")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not await _guard(update):
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    task = asyncio.create_task(_run_chat_turn(update, context, text))
    _ACTIVE_TASKS[chat_id] = task
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        _ACTIVE_TASKS.pop(chat_id, None)


async def _safe_edit(message, text: str) -> None:
    if not text.strip():
        text = "…"
    try:
        await message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        try:
            await message.edit_text(text)
        except Exception:
            pass  # message unchanged / rate limited — ignore
    except Exception:
        pass


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    state = _chat_state(context)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    content = bytes(await file.download_as_bytearray())
    filename = f"photo_{uuid.uuid4().hex[:8]}.jpg"

    await upload_file(state["session_id"], filename, content, "image/jpeg")
    caption = update.message.caption or "Describe this image and tell me what you notice."

    await update.message.reply_text(f"📎 Got your photo — analyzing with caption: _{caption}_", parse_mode=ParseMode.MARKDOWN)
    await on_message_with_text(update, context, caption)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    state = _chat_state(context)
    doc = update.message.document
    file = await doc.get_file()
    content = bytes(await file.download_as_bytearray())
    await upload_file(state["session_id"], doc.file_name, content, doc.mime_type or "application/octet-stream")
    await update.message.reply_text(f"📎 Uploaded *{doc.file_name}* into my workspace — ask me anything about it!", parse_mode=ParseMode.MARKDOWN)


async def on_message_with_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    fake_message = update.message
    fake_message.text = text
    await on_message(update, context)


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("start", "Welcome & quick menu"),
        BotCommand("new", "Start a fresh conversation"),
        BotCommand("imagine", "Generate an image from a text prompt"),
        BotCommand("mode", "Switch agent mode"),
        BotCommand("persona", "Switch persona"),
        BotCommand("providers", "Switch model provider"),
        BotCommand("model", "Pick a specific model (DeepSeek, Kimi, GLM, Qwen...)"),
        BotCommand("lang", "Set the language Meiko replies in"),
        BotCommand("memory", "See/clear what Meiko remembers about you"),
        BotCommand("connectors", "Toggle connectors (GitHub, Wikipedia...)"),
        BotCommand("skills", "List available skills"),
        BotCommand("github", "Set your GitHub token for read/write repo tools"),
        BotCommand("history", "Browse & resume past conversations"),
        BotCommand("rename", "Rename the current conversation"),
        BotCommand("usage", "See your usage stats"),
        BotCommand("stop", "Cancel the current response"),
        BotCommand("help", "Show help"),
    ])


def build_application() -> Application:
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set — see telegram-bot/.env.example")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("imagine", cmd_imagine))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("persona", cmd_persona))
    app.add_handler(CommandHandler("providers", cmd_providers))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("connectors", cmd_connectors))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("github", cmd_github))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("rename", cmd_rename))
    app.add_handler(CommandHandler("usage", cmd_usage))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    return app


def main() -> None:
    app = build_application()
    logger.info("Meiko Telegram bot starting (polling mode)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
