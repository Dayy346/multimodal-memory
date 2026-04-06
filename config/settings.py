"""Paths and constants for multimodal-memory pipelines."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
MANIFESTS_DIR = DATA_DIR / "manifests"
SAMPLES_DIR = DATA_DIR / "samples"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
THUMBNAILS_DIR = OUTPUTS_DIR / "thumbnails"
FRAMES_DIR = OUTPUTS_DIR / "frames"
CLIPS_DIR = OUTPUTS_DIR / "clips"
EMBEDDINGS_DIR = OUTPUTS_DIR / "embeddings"
METADATA_DIR = OUTPUTS_DIR / "metadata"
LOGS_DIR = OUTPUTS_DIR / "logs"

# Gemini Embedding 2 video: stay under ~120s per request; audio lowers the cap,
# so derived clips strip audio by default (original files on disk unchanged).
VIDEO_EMBED_MAX_SECONDS = float(os.environ.get("VIDEO_EMBED_MAX_SECONDS", "118"))
VIDEO_STRIP_AUDIO_ON_CLIPS = os.environ.get(
    "VIDEO_STRIP_AUDIO_ON_CLIPS", "true"
).lower() in ("1", "true", "yes")
EMBED_MANIFEST_NAME = "embed_manifest.jsonl"

IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
)
VIDEO_EXTENSIONS = frozenset(
    {
        ".mp4",
        ".mov",
        ".mkv",
        ".avi",
        ".webm",
        ".m4v",
        ".wmv",
        ".3gp",
    }
)

GEMINI_EMBEDDING_MODEL = os.environ.get(
    "GEMINI_EMBEDDING_MODEL", "gemini-embedding-2-preview"
)

_dims = os.environ.get("GEMINI_EMBEDDING_DIMENSIONALITY", "").strip()
EMBEDDING_OUTPUT_DIMENSIONALITY: int | None = (
    int(_dims) if _dims.isdigit() else None
)


def ensure_output_dirs() -> None:
    for d in (
        MANIFESTS_DIR,
        THUMBNAILS_DIR,
        FRAMES_DIR,
        CLIPS_DIR,
        EMBEDDINGS_DIR,
        METADATA_DIR,
        LOGS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
