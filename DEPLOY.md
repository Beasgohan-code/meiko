# Deploying Meiko publicly (free tier, ~5 minutes)

This gets you a **real public URL** (not just a local/sandbox preview) using only free tiers —
no credit card required. Two pieces: the **backend API** (Render) and the **web app** (Vercel).

> Note on custom domains: `meiko.ai.dev` / `meiko.dev.ai` style domains have to be purchased from a
> registrar (Namecheap, Porkbun, Google Domains successor, etc.) — nobody can grant you one for free,
> including AI tools. The good news: once you own *any* domain, pointing it at the deploy below is a
> 5-minute DNS change (see **Custom domain** section at the bottom). Until then, Vercel/Render give you
> a solid free subdomain like `meiko-yourname.vercel.app`.

## 1. Backend → Render.com (free web service)

1. Go to https://dashboard.render.com/blueprints and click **New Blueprint Instance**.
2. Connect your GitHub account and pick the `Beasgohan-code/meiko` repo (Render auto-detects
   `render.yaml` at the repo root and provisions the backend service + a persistent disk for the DB).
3. In the Render dashboard → your service → **Environment**, add at least one provider key so chat
   works out of the box for visitors, e.g.:
   - `NVIDIA_API_KEY` — free key from https://build.nvidia.com/
   - `GEMINI_API_KEY` — free key from https://aistudio.google.com/apikey
   - (Optional) `MEIKO_API_KEY` — set this if you want to require an API key header for your public API.
4. Deploy. Render gives you a URL like `https://meiko-backend.onrender.com` — copy it.
   - First request after idle may take ~30-50s to cold-start on the free tier; this is normal.

## 2. Web app → Vercel (free static hosting)

1. Go to https://vercel.com/new, sign in with GitHub, and **Import** the `Beasgohan-code/meiko` repo.
2. Set **Root Directory** to `web`.
3. Framework preset: **Vite** (auto-detected).
4. Add an environment variable:
   - `VITE_BACKEND_URL` = the Render backend URL from step 1, e.g. `https://meiko-backend.onrender.com`
5. Click **Deploy**. Vercel gives you a permanent URL like `https://meiko-yourname.vercel.app` in
   about 60 seconds, plus a preview URL on every future push to `main`.

That's it — share the Vercel URL. Anyone can open it, plug in their own free API key in
Settings, and start chatting with zero backend of their own needed.

## Alternative: Docker Compose (self-host anywhere with a VPS)

If you'd rather run everything on your own VPS/droplet:

```bash
git clone https://github.com/Beasgohan-code/meiko.git
cd meiko
cp backend/.env.example backend/.env   # add your free API key(s)
docker compose up -d --build
```

This starts backend (`:8000`), the web app behind nginx (`:3000`), and the Telegram bot together.
Put a reverse proxy (Caddy/nginx/Cloudflare Tunnel) with a real domain + TLS in front of port 3000
and 8000 for a fully custom-domain production deploy.

## Custom domain (once you own one)

Whichever host you use (Vercel, Render, or your own VPS + Caddy), the pattern is the same:
1. In your registrar's DNS panel, add a `CNAME` (or `A`, for VPS) record pointing your domain/subdomain
   at the host's target (Vercel/Render show you the exact value under **Domains** in their dashboard).
2. Add the domain in that host's dashboard and wait for the TLS certificate to auto-provision
   (usually a few minutes).
3. Update `VITE_BACKEND_URL` (web) and `CORS_ORIGINS` (backend) to match your final domain.
