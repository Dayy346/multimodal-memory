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

### Full stack (Docker — recommended on homelab)

1. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`. Set `NAS_MOUNT` to your host photo root (e.g. `/mnt/photos`) and `ALLOWED_SCAN_ROOTS` to folders under that same path inside the container (e.g. `/mnt/photos/photos`).
2. `make up` — builds and starts **Postgres**, **FastAPI**, and **web UI** (nginx). Migrations run automatically on API start.
3. Open **http://\<server-ip\>:5173** (or `WEB_PORT` from `.env`). All `/api` calls go through the same origin — no second terminal.

Other commands: `make down`, `make logs`, `make rebuild`, `make db-migrate`.

### Local dev without Docker (optional)

1. `make up` — Postgres only, or use your own DB  
2. `make db-migrate`  
3. `make api` — FastAPI on port 8000  
4. `make dev-frontend` — Vite on 5173 (proxies `/api` to the API)

Pipeline overview, Gemini video limits, and server (NAS) workflow: [docs/PIPELINE.md](docs/PIPELINE.md).
