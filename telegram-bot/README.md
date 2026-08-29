# Meiko Telegram Bot

A full-featured Telegram client for the Meiko agent, built on modern
[python-telegram-bot](https://docs.python-telegram-bot.org/) (Bot API 7+).

## Features
- 🧭 `/mode` — switch agent mode (Chat/Research/Code/Autonomous/Creative) via inline buttons
- 🎭 `/persona` — switch persona (Engineer, Researcher, Writer, Tutor, PM, Security Reviewer…)
- 🔑 `/providers` — see available free/paid model providers
- 🆕 `/new` — reset the conversation
- 💬 Live-streamed replies: the bot edits a single message progressively as Meiko thinks/uses tools/answers,
  showing a real-time "🔧 using tool_name…" trace, just like the web app
- 📎 Photo & document upload — forwarded straight into Meiko's sandboxed session workspace
- 🌐 Optional **Telegram Web App** button that opens the full Meiko web app inside Telegram
- 🗂 Per-chat conversation + session continuity (each Telegram chat keeps its own Meiko session)

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN` and `MEIKO_BACKEND_URL`
   (point it at your running Meiko backend, e.g. `http://localhost:8000` or your deployed URL).
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the bot:

```bash
python run.py
```

## Docker

```bash
docker build -t meiko-telegram-bot .
docker run --env-file .env meiko-telegram-bot
```

## Notes
- The bot talks to the Meiko backend's `/api/chat/stream` SSE endpoint, so make sure the backend
  is reachable from wherever the bot runs.
- To enable the "Open Meiko Web App" button, set `MEIKO_WEBAPP_URL` to your HTTPS-hosted web app URL
  (Telegram requires HTTPS for Web Apps).
