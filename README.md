# multimodal-memory

Project scaffold for multimodal memory (app, scripts, config, data, outputs).

## Layout

- `app/` — FastAPI backend (`app/main.py`, `app/api/`, `app/db/`, `app/services/`)
- `frontend/` — Vue 3 + TypeScript + Vite UI
- `multimodal_memory/` — shared scan / preprocess / embed logic (used by scripts + API)
- `scripts/` — CLI wrappers around `multimodal_memory`
- `config/` — paths and pipeline constants
- `alembic/` — Postgres + pgvector migrations
- `data/manifests/` — dataset manifests
- `data/samples/` — small local samples (large blobs stay gitignored by default)
- `outputs/` — generated logs, job workspaces under `outputs/jobs/`, thumbnails, clips, metadata

Edit `.env` for local secrets (listed in `.gitignore` so it is not committed).

### Full-stack dev (Postgres + API + UI)

1. `make up` — start Postgres (pgvector) via Docker Compose  
2. `make db-migrate` — apply Alembic migrations  
3. `make api` — run FastAPI on port 8000  
4. `make dev-frontend` — Vite dev server on 5173 (proxies `/api` to the API)

Set `GEMINI_API_KEY`, `DATABASE_URL`, and comma-separated `ALLOWED_SCAN_ROOTS` in `.env` (see `.env.example`).

Pipeline overview, Gemini video limits, and server (NAS) workflow: [docs/PIPELINE.md](docs/PIPELINE.md).
