# 🌀 Meiko — Your Open, Pluggable Autonomous AI Agent

Meiko is a full-stack, open AI agent platform — a **web app**, a **Flutter mobile app**, and a
**Telegram bot**, all backed by one shared FastAPI agent harness. Bring your own free API key
(NVIDIA NIM, Google Gemini, OpenRouter, Groq, Cerebras, Hugging Face, Mistral) or run fully local
with Ollama — Meiko will research the web, write & execute code, generate images, remember things
about you, and call out to connectors/plugins (GitHub, Wikipedia, Reddit, Hacker News, Weather),
much like Claude's Connectors or a DeepSeek-style agent harness.

## ✨ Highlights

- 🧠 **Full autonomous agent harness** — planning loop, tool-calling, memory, and 5 built-in
  **Agent Modes**: Chat, Research, Code, Autonomous, Creative
- 🔌 **Connector/Plugin framework** — JSON-manifest connectors (no code needed to add a new API);
  ships with GitHub, Wikipedia, Reddit, Hacker News, and Open-Meteo Weather
- 🎭 **Persona library** — Engineer, Research Analyst, Creative Writer, Tutor, Product Strategist,
  Security Reviewer, or write your own custom instructions
- 🔑 **Bring-your-own-key, zero lock-in** — pluggable provider layer supporting NVIDIA NIM, Gemini,
  OpenRouter, Groq, Cerebras, Hugging Face, Mistral, OpenAI, or local Ollama; keys can be set via
  `.env` **or** typed directly into the Settings UI in the app
- 🛠️ **Real tool use** — live web search, URL reading, a sandboxed Python execution tool, file
  read/write, image generation, `.md`/`.py` document export, and one-click `.zip` packaging of
  everything an agent run produced
- 🌐 **Web app** — React + TypeScript + **Three.js** (animated 3D "Meiko orb" avatar) + **anime.js**
  micro-interactions, streaming chat with live tool-trace visualization
- 📱 **Android/iOS app** — Flutter, same visual language, native animated orb, built automatically
  into an APK by GitHub Actions on every push
- 🤖 **Telegram bot** — modern Bot API 7+ features: inline keyboards for modes/personas, live
  streaming message edits, photo/document upload, optional Web App launch button
- 🧑‍💻 **CLI** — talk to Meiko, switch modes, manage keys, and download generated files from the
  terminal
- ⚙️ **CI/CD** — GitHub Actions build/test every component, and automatically build signed/unsigned
  Android APKs plus a full release bundle zip

## 📁 Project layout

```
meiko/
├── backend/          FastAPI agent harness (providers, tools, plugins, agent modes, personas)
│   └── plugins/      JSON connector manifests (GitHub, Wikipedia, Reddit, Hacker News, Weather)
├── web/              React + Three.js + anime.js web app
├── mobile/           Flutter Android/iOS app
├── telegram-bot/     python-telegram-bot client
├── cli/              Terminal client for the Meiko backend
└── .github/workflows/  CI/CD: backend, web, telegram bot, Android APK build, full release bundler
```

## 🚀 Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add a free API key, e.g. NVIDIA_API_KEY=nvapi-...
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Get a **free** API key from any of these (no credit card needed for the free tiers):
- NVIDIA NIM: https://build.nvidia.com/
- Google Gemini: https://aistudio.google.com/apikey
- OpenRouter: https://openrouter.ai/keys
- Groq: https://console.groq.com/keys
- Cerebras: https://cloud.cerebras.ai/
- Hugging Face: https://huggingface.co/settings/tokens
- Mistral: https://console.mistral.ai/api-keys

You can also skip `.env` entirely and paste a key directly into the web/mobile app's **Settings**
screen — it's stored server-side per user.

### 2. Web app

```bash
cd web
npm install
npm run dev
```

Visit the printed local URL. The dev server proxies `/api/*` to `http://localhost:8000` automatically.

### 3. Telegram bot

```bash
cd telegram-bot
pip install -r requirements.txt
cp .env.example .env   # add TELEGRAM_BOT_TOKEN from @BotFather + MEIKO_BACKEND_URL
python run.py
```

### 4. Mobile app

```bash
cd mobile
flutter pub get
flutter run
```

Set the backend URL in-app under **Settings → Server & Persona** (defaults to the Android
emulator's localhost alias `http://10.0.2.2:8000`).

### 5. CLI

```bash
cd cli
pip install -r requirements.txt
python meiko_cli.py chat "hello Meiko!"
```

## 🤖 CI/CD

Every push runs the relevant CI workflow (`backend-ci.yml`, `web-ci.yml`, `telegram-bot-ci.yml`).
`android-build.yml` builds a debug + release APK on every push to `mobile/**` and uploads them as
downloadable workflow artifacts — grab them from the **Actions** tab, or trigger a GitHub Release
to get them attached automatically. `release.yml` bundles the entire built stack (web dist + APK +
backend + bot + CLI source) into one zip for easy self-hosting.

### Optional: signed release APKs

To get properly signed release APKs instead of debug-signed ones, add these repository secrets
(Settings → Secrets and variables → Actions):

- `ANDROID_KEYSTORE_BASE64` — your `.jks` keystore, base64-encoded (`base64 -w0 your.jks`)
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_PASSWORD`
- `ANDROID_KEY_ALIAS`

## 🔌 Adding a new connector

Drop a JSON manifest into `backend/plugins/your_connector.json` describing the API's base URL,
auth, and actions (see `backend/plugins/github.json` for a full example) — no Python code required.
Meiko will pick it up automatically and expose it as a tool the agent can call.

## 🎭 Agent Modes

| Mode | What it does |
|---|---|
| **Chat** | Fast, tool-free conversational replies |
| **Research** | Proactively searches + reads the web, cites sources |
| **Code** | Writes, runs, and debugs code in a sandboxed workspace |
| **Autonomous** | Full tool access, plans and executes multi-step tasks |
| **Creative** | Image generation + creative writing focus |

## 🙏 Credits & inspiration

Meiko's connector framework, persona library, and free-provider catalog were inspired in part by
the open-source community, including
[awesome-freellm-apis](https://github.com/open-free-llm-api/awesome-freellm-apis),
[agency-agents](https://github.com/msitarzewski/agency-agents), and
[Agent-Reach](https://github.com/Panniantong/Agent-Reach).

## 📄 License

MIT — see [LICENSE](LICENSE).
