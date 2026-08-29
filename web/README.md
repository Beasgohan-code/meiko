# Meiko Web App

React + TypeScript + Three.js + anime.js frontend for the Meiko agent.

## Features
- 🌀 Living 3D "Meiko orb" avatar (Three.js) that reacts to agent state (idle / thinking / using a tool / speaking)
- ✨ Smooth anime.js micro-interactions (message entrances, hero intro, button pulses, thinking dots)
- 🧵 Real-time streaming chat via Server-Sent Events, with live tool-call trace visualization
- 🧠 Agent Mode switcher (Chat / Research / Code / Autonomous / Creative)
- 🎭 Persona library + custom persona instructions
- 🔌 Connector/plugin manager (enable/disable GitHub, Wikipedia, Reddit, Hacker News, Weather, or add your own)
- 🔑 In-app Settings to paste your own free API keys (NVIDIA NIM, Gemini, OpenRouter, Groq, Cerebras, Hugging Face, Mistral) or point at local Ollama
- 📎 File/image upload support
- 📱 Responsive layout (collapsible sidebar on mobile)

## Development

```bash
npm install
npm run dev
```

By default the Vite dev server proxies `/api/*` requests to `http://localhost:8000` (the Meiko backend).
Override with `VITE_BACKEND_URL` in a `.env` file if your backend runs elsewhere.

## Production build

```bash
npm run build
npm run preview
```

Outputs a static `dist/` folder you can serve from any static host (Vercel, Netlify, Cloudflare Pages,
GitHub Pages, or the Meiko backend's built-in static file server).
