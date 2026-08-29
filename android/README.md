# Meiko — Native Android (Kotlin)

A standalone, from-scratch native Android client for the Meiko agent harness, written in
**Kotlin + Jetpack Compose + Material 3**. It talks to the same FastAPI backend as the web app,
the Flutter app, and the Telegram bot (`GET/POST /api/*` under `backend/app/main.py`), and mirrors
their feature set:

- Agent modes (Chat / Research / Code / Autonomous / Creative), selectable per turn
- Provider + model picker — NVIDIA NIM's full free multi-model catalog (`/api/models`), plus
  Gemini, OpenRouter, Groq, OpenAI, and local Ollama, each with its own bring-your-own-key field
- Persona library and a reply-language selector (12 languages) that nudges every response
- Streaming chat over Server-Sent Events (`/api/chat/stream`) with a live plan/checklist tracker,
  tool-call traces, citation chips, and automatic-provider-fallback notices
- Persistent memory manager (view/delete/clear facts Meiko has learned about you)
- Conversation history with search, rename, pin, and delete
- Generated-image rendering inline in the chat, downloaded via `/api/download/{session}/{file}`
- An animated gradient "orb" avatar (idle / thinking / speaking / tool states) built with pure
  Compose animations — no external animation engine required

This module is **independent of `mobile/` (the Flutter app)** — both are shipped and maintained
side by side per product requirements; this is not a replacement.

## Stack

- Kotlin, Jetpack Compose (BOM `2024.06.00`), Material 3, Navigation-Compose
- Ktor client (CIO engine) for HTTP + raw SSE line streaming
- kotlinx.serialization for JSON
- Coil for image loading, `compose-markdown` for rendering agent replies
- Jetpack DataStore (Preferences) for local settings persistence
- Gradle 8.7 / AGP 8.5.2 / Kotlin 1.9.24, `compileSdk`/`targetSdk` 34, `minSdk` 26

## Building

This sandbox has no local Android SDK, so the app is validated exclusively via CI
(`.github/workflows/android-native-build.yml`), which runs on every push to `android/**`:

```
cd android
./gradlew assembleDebug
./gradlew assembleRelease
```

To build locally with Android Studio: open the `android/` folder as a project, let Gradle sync,
then Run. Point the app at your backend by editing the `DEFAULT_BACKEND_URL` build config field in
`app/build.gradle.kts`, or override it at runtime from the in-app Settings screen (persisted via
DataStore, no rebuild needed).

## Structure

```
android/
├── app/
│   └── src/main/java/ai/meiko/app/
│       ├── MainActivity.kt        Compose entry point
│       ├── MeikoApp.kt            Application class
│       ├── data/                  API client (Ktor), models, DataStore prefs
│       └── ui/
│           ├── MeikoViewModel.kt  Central state holder + SSE event reducer
│           ├── chat/              Chat screen, message bubbles, composer, orb avatar
│           ├── settings/          Providers/models/persona/memory/skills tabs
│           ├── history/           Conversation history + search
│           └── theme/             Color tokens + MaterialTheme wiring
├── build.gradle.kts / settings.gradle.kts / gradle.properties
└── gradlew / gradle/wrapper/      Gradle 8.7 wrapper (CI-only build path)
```

## Signing release builds

Same repository secrets as the Flutter workflow (`ANDROID_KEYSTORE_BASE64`,
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_PASSWORD`, `ANDROID_KEY_ALIAS`) are consumed by
`android-native-build.yml` to sign release APKs; without them, release builds fall back to a
debug-signed APK so CI always succeeds.
