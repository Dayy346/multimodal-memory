# multimodal-memory

Project scaffold for multimodal memory (app, scripts, config, data, outputs).

Embeddings run **locally** with [`jinaai/jina-embeddings-v5-omni-small`](https://huggingface.co/jinaai/jina-embeddings-v5-omni-small) (text, image, video in one 1024-d space). No Gemini API key. The model is CC BY-NC 4.0.

Give the API process **~8 GB RAM** (Docker Desktop memory slider on Windows). The first run downloads about 4 GB of weights into the Hugging Face cache. Runtime extras include `peft` and `torchvision` (needed for the vision processor).

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

Edit `.env` for local paths (listed in `.gitignore` so it is not committed).

### Full stack (Docker — recommended on homelab)

1. Copy `.env.example` to `.env`. Set `NAS_MOUNT` to your host photo root (e.g. `/mnt/photos`) and `ALLOWED_SCAN_ROOTS` to folders under that same path inside the container (e.g. `/mnt/photos/photos`).
2. `make up` — builds and starts **Postgres**, **FastAPI**, and **web UI** (nginx). Migrations run automatically on API start. Old Gemini vectors are dropped (1024-d Jina space); re-index after upgrading.
3. Open **http://\<server-ip\>:5173** (or `WEB_PORT` from `.env`). All `/api` calls go through the same origin — no second terminal.
4. Optional: **Settings → Load model** so the first index/search is not stuck on the weight download.

**Extend** (`/extend`): add vectors to an existing index; skips duplicate `embed_id`.

Other commands: `make down`, `make logs`, `make rebuild`, `make db-migrate`.

**HEIC thumbnails on an old job** (after rebuilding API with HEIC support):

```bash
docker compose up -d --build api
JOB_ID=8a8c6bbd-83e2-43f8-9935-b93798a19572 make backfill-thumbs
```

Or: `docker compose exec api python scripts/backfill_thumbnails.py --job-id <uuid> --heic-only`

### Local dev without Docker (optional)

1. `make up` — Postgres only, or use your own DB
2. `python -m pip install -r requirements.txt` (install a CUDA `torch` from pytorch.org first if you have an NVIDIA GPU)
3. `make db-migrate`
4. `make api` — FastAPI on port 8000
5. `make dev-frontend` — Vite on 5173 (proxies `/api` to the API)

Confirm the encoder (first run downloads ~4 GB):

```bash
python scripts/smoke_embed.py
```

Pipeline overview and server (NAS) workflow: [docs/PIPELINE.md](docs/PIPELINE.md).
