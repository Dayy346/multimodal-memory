# multimodal-memory

Project scaffold for multimodal memory (app, scripts, config, data, outputs).

## Layout

- `app/` — application code
- `scripts/` — one-off utilities and pipelines
- `config/` — configuration files
- `data/manifests/` — dataset manifests
- `data/samples/` — small local samples (large blobs stay gitignored by default)
- `outputs/` — generated logs, embeddings, thumbnails, frames, metadata

Edit `.env` for local secrets (listed in `.gitignore` so it is not committed).

Pipeline overview, Gemini video limits, and server (NAS) workflow: [docs/PIPELINE.md](docs/PIPELINE.md).
