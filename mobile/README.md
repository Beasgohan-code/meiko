# Meiko Mobile App (Flutter)

The native Android/iOS client for the Meiko agent, visually consistent with the web app
(same violet/cyan dark theme, same living animated orb avatar — implemented natively with a
`CustomPainter` since Flutter doesn't run Three.js).

## Features
- 🌀 Native animated "Meiko orb" avatar reacting to agent state
- 🧵 Real-time streaming chat via SSE, with live tool-call trace
- 🧭 Agent Mode + Persona switcher (drawer menu)
- 🔌 Connector manager (enable/disable GitHub, Wikipedia, Reddit, Hacker News, Weather)
- 🔑 In-app Settings — paste your own free API keys (NVIDIA NIM, Gemini, OpenRouter, Groq,
  Cerebras, Hugging Face, Mistral), or point at your self-hosted Ollama
- 📎 Image/document upload from camera roll or file picker
- ⚙️ Configurable backend URL (works with local dev server or your deployed Meiko backend)

## Development

```bash
flutter pub get
flutter run
```

Point the app at your Meiko backend from the in-app **Settings → Server & Persona** tab.
Defaults to `http://10.0.2.2:8000` (Android emulator's alias for the host machine's localhost).

## Building an APK locally

```bash
flutter build apk --release
```

Output: `build/app/outputs/flutter-apk/app-release.apk`

## CI builds

This repo's GitHub Actions workflow (`.github/workflows/android-build.yml`) automatically builds
a debug + release APK on every push to `main` and on tagged releases, uploading them as workflow
artifacts (and attaching to GitHub Releases for tags). See the root `README.md` for details.

## App icon

Regenerate launcher icons after changing `assets/icon.png`:

```bash
dart run flutter_launcher_icons
```
