# Deployment

The whole app (FastAPI backend + React frontend + local ML models) ships as a
single Docker image. The frontend is built and served by the backend, so there
is **one container, one port (8000)**.

## Run locally with Docker

```bash
# 1. Make sure .env contains your key:
#    GROQ_API_KEY=gsk_...
# 2. Build + start
docker compose up -d --build
# 3. Open the app
#    http://localhost:8000
```

Useful commands:

```bash
docker compose logs -f          # tail logs
docker compose restart          # restart
docker compose down             # stop & remove container (data/ volume persists)
docker compose up -d --build    # rebuild after code changes
```

Data (Chroma vectors, SQLite DB, uploads) lives in `./data`, mounted as a volume,
so it survives restarts and rebuilds.

## Share a public link (fastest — from your machine)

Run the container, then expose port 8000 with a tunnel:

```bash
# Cloudflare quick tunnel (no account needed) — gives a https://*.trycloudflare.com URL
cloudflared tunnel --url http://localhost:8000

# …or ngrok
ngrok http 8000
```

Paste the printed URL into your resume / share it. (The machine must stay on.)

## Permanent free hosting

This image loads ~300 MB of ML models into RAM, so pick a host with enough memory:

| Host | Free tier | Notes |
|------|-----------|-------|
| **Hugging Face Spaces (Docker SDK)** | 16 GB RAM | Best fit. Push repo, set `GROQ_API_KEY` as a Space secret, expose port 8000. |
| Render (Web Service, Docker) | 512 MB | Tight — may OOM loading models. |
| Fly.io | small VMs | Set `GROQ_API_KEY` via `fly secrets set`; add a volume for `/app/data`. |

Set `GROQ_API_KEY` as a secret/env var on whichever host you choose — never bake
it into the image.
