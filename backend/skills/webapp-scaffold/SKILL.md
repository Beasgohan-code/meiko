---
name: Web App Scaffolder
description: Scaffold a small, working single-page web app (HTML/CSS/JS or React) from a description, ready to preview or ship.
triggers: [website, web app, landing page, html page, react app, single page app]
---

# Web App Scaffolder

When asked to build a website, landing page, or small web app:

1. Prefer a **single self-contained HTML file** (inline `<style>` and `<script>`) unless the user explicitly
   asks for a multi-file React/Vite project — this previews instantly and has zero build step.
2. Use `write_file` to create `index.html` in the workspace. Include:
   - Semantic HTML structure (header/nav/main/footer).
   - Modern CSS: flexbox/grid layout, a coherent color palette, responsive breakpoints, smooth transitions.
   - Vanilla JS for any interactivity — no external CDN scripts (the in-app preview has no network access),
     so keep everything inline/embedded (inline SVGs instead of icon fonts, data URIs instead of remote images).
3. If a multi-file React project is explicitly requested, use `write_file` for each file
   (`package.json`, `src/App.jsx`, etc.) and `run_bash` to `npm install` and `npm run build` to verify it compiles.
4. Always sanity-check your HTML/JS: use `run_bash` with a quick `python3 -m http.server` smoke check or a
   linter if available, and re-read the file with `read_file` to confirm the final content before finishing.
5. Offer to zip the whole project with `make_zip` if it has multiple files, so the user can download and
   run it locally with real network access.
