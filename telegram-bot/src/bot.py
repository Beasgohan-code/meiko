"""
Meiko Telegram Bot — full-featured client for the Meiko agent harness.

Uses modern python-telegram-bot v21 (Bot API 7+) features:
  - Inline keyboards for mode/persona switching
  - Live-edited "typing" style streaming responses (progressively edits one message)
  - Command menu (/start, /mode, /persona, /new, /providers, /help)
  - Photo & document upload support (forwarded into Meiko's session workspace)
  - Web App / mini-app launch button (if MEIKO_WEBAPP_URL is configured)
  - MarkdownV2-safe rendering with graceful fallback to plain text
  - Per-chat conversation + session continuity
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatAction, ParseMode
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
    download_url,
    fetch_modes,
    fetch_personas,
    fetch_providers,
    set_user_settings,
    stream_chat,
    upload_file,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("meiko-bot")

MODE_EMOJI = {
    "chat": "💬", "research": "🔎", "code": "💻", "autonomous": "🤖", "creative": "🎨",
}


def _chat_state(context: ContextTypes.DEFAULT_TYPE) -> dict:
    context.user_data.setdefault("mode", "autonomous")
    context.user_data.setdefault("persona_id", "default")
    context.user_data.setdefault("conversation_id", None)
    context.user_data.setdefault("session_id", str(uuid.uuid4()))
    return context.user_data


def _user_id(update: Update) -> str:
    return f"tg-{update.effective_user.id}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _chat_state(context)
    buttons = [
        [InlineKeyboardButton("🧭 Choose Agent Mode", callback_data="menu:mode")],
        [InlineKeyboardButton("🎭 Choose Persona", callback_data="menu:persona")],
        [InlineKeyboardButton("🔑 Model Providers", callback_data="menu:providers")],
    ]
    if config.WEBAPP_URL:
        buttons.append([InlineKeyboardButton("🌐 Open Meiko Web App", web_app=WebAppInfo(url=config.WEBAPP_URL))])

    await update.message.reply_text(
        "👋 *Hey, I'm Meiko!*\n\n"
        "Your open, pluggable autonomous AI agent — I can research the web, write & run code, "
        "generate images, remember things about you, and use connectors (GitHub, Wikipedia, Reddit, "
        "Hacker News, Weather).\n\n"
        "Just send me a message to get started, or use the menu below to switch modes/personas.\n\n"
        "*Commands:*\n"
        "/mode – switch agent mode\n"
        "/persona – switch persona\n"
        "/new – start a fresh conversation\n"
        "/providers – see/set your model provider\n"
        "/help – show this again",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _chat_state(context)
    state["conversation_id"] = None
    state["session_id"] = str(uuid.uuid4())
    await update.message.reply_text("🆕 Started a fresh conversation. What's on your mind?")


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    modes = await fetch_modes()
    buttons = [
        [InlineKeyboardButton(f"{MODE_EMOJI.get(m['id'], '✨')} {m['name']} — {m['description'][:40]}", callback_data=f"mode:{m['id']}")]
        for m in modes
    ]
    await update.message.reply_text("Pick an agent mode:", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_persona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    personas = await fetch_personas()
    buttons = [
        [InlineKeyboardButton(f"{p['name']} — {p['tagline'][:40]}", callback_data=f"persona:{p['id']}")]
        for p in personas
    ]
    await update.message.reply_text("Pick a persona:", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_providers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    providers = await fetch_providers()
    lines = ["*Available model providers* (set your key via the Meiko web app Settings for full control):\n"]
    for p in providers:
        badge = "🆓" if p.get("free_tier") else "💳"
        lines.append(f"{badge} `{p['id']}` — {p['display_name']}: {p['description']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    state = _chat_state(context)

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
        text = "\n".join(f"{'🆓' if p.get('free_tier') else '💳'} {p['display_name']}" for p in providers)
        await query.edit_message_text(f"Providers:\n{text}\n\nConfigure keys in the Meiko web app → Settings.")
    elif data.startswith("mode:"):
        mode_id = data.split(":", 1)[1]
        state["mode"] = mode_id
        await query.edit_message_text(f"✅ Agent mode set to *{mode_id}*.", parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("persona:"):
        persona_id = data.split(":", 1)[1]
        state["persona_id"] = persona_id
        await query.edit_message_text(f"✅ Persona set to *{persona_id}*.", parse_mode=ParseMode.MARKDOWN)


def _escape_md(text: str) -> str:
    # Lightweight escaping for Telegram MarkdownV2 special chars, used only as a fallback.
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    state = _chat_state(context)
    user_id = _user_id(update)
    text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    placeholder = await update.message.reply_text("💭 _Meiko is thinking…_", parse_mode=ParseMode.MARKDOWN)

    buffer = ""
    tool_lines: list[str] = []
    last_edit = 0.0
    final_text = ""
    new_conversation_id = None

    try:
        async for event in stream_chat(
            user_id,
            text,
            mode=state["mode"],
            conversation_id=state["conversation_id"],
            session_id=state["session_id"],
            persona_id=state["persona_id"],
        ):
            etype = event.get("type")
            if etype == "tool_call":
                tool_lines.append(f"🔧 using `{event.get('name')}`…")
                now = time.time()
                if now - last_edit > config.EDIT_THROTTLE_SECONDS:
                    await _safe_edit(placeholder, "\n".join(tool_lines[-4:]) + ("\n\n" + buffer if buffer else ""))
                    last_edit = now
            elif etype == "token":
                buffer += event.get("text", "")
                now = time.time()
                if now - last_edit > config.EDIT_THROTTLE_SECONDS:
                    display = ("\n".join(tool_lines[-2:]) + "\n\n" if tool_lines else "") + buffer
                    await _safe_edit(placeholder, display[-3800:])
                    last_edit = now
            elif etype == "final":
                final_text = event.get("text", buffer)
            elif etype == "error":
                await _safe_edit(placeholder, f"⚠️ Error: {event.get('message')}")
                return
            elif etype == "done":
                new_conversation_id = event.get("conversation_id")

        display_final = final_text or buffer or "…"
        await _safe_edit(placeholder, display_final[:4000])

        if new_conversation_id and not state["conversation_id"]:
            state["conversation_id"] = new_conversation_id

    except Exception as e:  # noqa: BLE001
        logger.exception("chat stream failed")
        await _safe_edit(placeholder, f"⚠️ Something went wrong talking to Meiko's backend: {e}")


async def _safe_edit(message, text: str) -> None:
    if not text.strip():
        text = "…"
    try:
        await message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        try:
            await message.edit_text(text)
        except Exception:
            pass  # message unchanged / rate limited — ignore


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _chat_state(context)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    content = bytes(await file.download_as_bytearray())
    filename = f"photo_{uuid.uuid4().hex[:8]}.jpg"

    result = await upload_file(state["session_id"], filename, content, "image/jpeg")
    caption = update.message.caption or "Describe this image and tell me what you notice."

    await update.message.reply_text(f"📎 Got your photo — analyzing with caption: _{caption}_", parse_mode=ParseMode.MARKDOWN)
    # Forward as a normal chat turn so the agent harness can reason about it (vision-capable providers will see it via image_paths in a future enhancement)
    await on_message_with_text(update, context, caption)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _chat_state(context)
    doc = update.message.document
    file = await doc.get_file()
    content = bytes(await file.download_as_bytearray())
    result = await upload_file(state["session_id"], doc.file_name, content, doc.mime_type or "application/octet-stream")
    await update.message.reply_text(f"📎 Uploaded *{doc.file_name}* into my workspace — ask me anything about it!", parse_mode=ParseMode.MARKDOWN)


async def on_message_with_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    fake_message = update.message
    fake_message.text = text
    await on_message(update, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


def build_application() -> Application:
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set — see telegram-bot/.env.example")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("persona", cmd_persona))
    app.add_handler(CommandHandler("providers", cmd_providers))
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
