# Multimodal memory pipeline (how it fits together)

## What you are building

1. **Inventory** every photo and video on disk (paths, sizes).
2. **Prepare embed targets** the local Jina model can encode:
   - **Images**: the **original file** (thumbnails are only for you to preview).
   - **Videos**: either the **whole file** if it is short enough, or **derived `.mp4` clips** (your originals stay untouched on the NAS).
3. **Embed** each target once with `jina-embeddings-v5-omni-small`, then **compare** text queries to those vectors to see what matches.

Retrieval answers in terms of **source file + time range** when a hit comes from a clip, so you can open the original video and jump to that segment in a player.

## Local Jina embeddings

The API loads [`jinaai/jina-embeddings-v5-omni-small`](https://huggingface.co/jinaai/jina-embeddings-v5-omni-small) in-process (sentence-transformers, `default_task=retrieval`). Queries use `encode_query`; catalog items use `encode_document`. Vectors are **1024-d** (optional Matryoshka truncate via `EMBEDDING_TRUNCATE_DIM`).

`EMBEDDING_MODALITY=vision` (default) loads text + vision and skips the audio tower to save RAM. First load downloads ~4 GB into the Hugging Face cache (`HF_HOME` in Docker).

Video clips still default to **118 seconds** so search hits keep a useful time range. That is not an API length cap.

## Files in this repo (tour)

| Path | Role |
|------|------|
| `config/settings.py` | Folders, allowed extensions, `EMBEDDING_MODEL`, `VIDEO_EMBED_MAX_SECONDS`, etc. |
| `scripts/build_manifest.py` | Recursively scan `--scan` roots → `data/manifests/media_manifest.jsonl`. |
| `scripts/preprocess_media.py` | Reads that manifest; writes thumbnails/posters; builds **`outputs/metadata/embed_manifest.jsonl`** (one line = one embed target). |
| `scripts/test_embeddings.py` | Reads `embed_manifest.jsonl`, runs the local model, prints ranked hits; saves `outputs/logs/embedding_probe.json`. |
| `requirements.txt` | Python dependencies (includes torch / transformers / sentence-transformers). |
| `.env` / `.env.example` | Model, DB URL, `ALLOWED_SCAN_ROOTS`, CORS (not committed). |
| `docker-compose.yml` / `Makefile` | `make up` — Postgres, API, and web UI in Docker (one command). |
| `frontend/` | Vue + TypeScript UI for picking allowed roots, watching jobs, and searching. |

Generated (gitignored): `outputs/thumbnails/`, `outputs/clips/`, `outputs/frames/` (fallback only), `outputs/metadata/`, `outputs/logs/`, `outputs/jobs/<job_id>/` (per-indexing workspace).

## Full-stack mode (MVP)

The FastAPI app exposes:

- `GET /api/roots` — allowed scan directories from `ALLOWED_SCAN_ROOTS`
- `POST /api/jobs` — start a background indexing job (scan → preprocess → embed → pgvector)
- `GET /api/jobs` / `GET /api/jobs/{id}` — list and poll job status
- `POST /api/query` — text search against embeddings for a completed job
- `GET /api/settings/embedding` — local model status; `POST /api/settings/embedding/load` warms it up
- `GET /api/jobs/{id}/media/thumbnail/{asset_id}` and `.../clip/{embed_target_id}` — previews

Run `make up` and open the web UI on port `WEB_PORT` (default 5173). See root `README.md`.

## Run order (on your home server, option B)

Clone the repo on the machine that can **see the NAS paths** (mount under Linux, e.g. `/mnt/nas/photos`).

```bash
cd multimodal-memory
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Install **ffmpeg** and **ffprobe** on the server (`apt install ffmpeg` on Debian/Ubuntu). No API key.

```bash
python scripts/build_manifest.py --scan /mnt/nas/photos --limit 200
python scripts/preprocess_media.py --manifest data/manifests/media_manifest.jsonl --max-videos 10
python scripts/test_embeddings.py
```

- **`--limit` / `--max-videos`**: keep the first run small while the model loads.
- If ffmpeg is missing, either install it or use `--fallback-frames 5` (JPEG frames; weaker than real video clips).

### ffmpeg timeouts (large libraries / NAS)

Preprocess **skips** a video segment when ffmpeg times out instead of failing the whole job. Optional `.env` knobs:

| Variable | Default | Purpose |
|----------|---------|---------|
| `FFMPEG_SEGMENT_TIMEOUT_SEC` | `1800` | Max seconds per clip segment (copy or re-encode) |
| `FFMPEG_FRAME_TIMEOUT_SEC` | `300` | Poster / fallback frame extraction |
| `FFPROBE_TIMEOUT_SEC` | `120` | Duration probe |
| `FFMPEG_CLIP_TRY_COPY` | `true` | Try fast `-c:v copy` before libx264 re-encode |

iPhone `.mov` on network storage often needs copy mode; re-encoding 118s can exceed 10 minutes.

## Legacy mode

`python scripts/test_embeddings.py --legacy-glob` uses old JPEG-only globs instead of `embed_manifest.jsonl`.

## What “originals preserved” means

- Images: embedding reads from the **source path** (HEIC/HEIF opened via pillow-heif; thumbnails saved as JPEG for the browser).
- Videos: long files are **not overwritten**; new files appear only under **`outputs/clips/`** (plus optional posters under `outputs/thumbnails/`).
