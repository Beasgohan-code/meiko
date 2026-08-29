"""Meiko Telegram Bot — configuration."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MEIKO_BACKEND_URL = os.environ.get("MEIKO_BACKEND_URL", "http://localhost:8000")
MEIKO_API_KEY = os.environ.get("MEIKO_API_KEY", "")
WEBAPP_URL = os.environ.get("MEIKO_WEBAPP_URL", "")  # optional: link to the hosted web app / Telegram Mini App
EDIT_THROTTLE_SECONDS = float(os.environ.get("EDIT_THROTTLE_SECONDS", "0.9"))

# Optional: comma-separated Telegram numeric user ids allowed to use the bot.
# Leave empty to allow anyone to use it (each user brings/uses their own configured provider keys).
ALLOWED_USER_IDS = {
    int(x) for x in os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if x.strip().isdigit()
}

if not TELEGRAM_BOT_TOKEN:
    print("[WARN] TELEGRAM_BOT_TOKEN is not set. Set it in telegram-bot/.env before running the bot.")
