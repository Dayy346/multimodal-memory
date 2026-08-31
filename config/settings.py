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
JOBS_DIR = OUTPUTS_DIR / "jobs"
THUMBNAILS_DIR = OUTPUTS_DIR / "thumbnails"
FRAMES_DIR = OUTPUTS_DIR / "frames"
CLIPS_DIR = OUTPUTS_DIR / "clips"
EMBEDDINGS_DIR = OUTPUTS_DIR / "embeddings"
METADATA_DIR = OUTPUTS_DIR / "metadata"
LOGS_DIR = OUTPUTS_DIR / "logs"

# Video clips stay short so search hits keep a useful time range (not an API limit).
VIDEO_EMBED_MAX_SECONDS = float(os.environ.get("VIDEO_EMBED_MAX_SECONDS", "118"))
VIDEO_STRIP_AUDIO_ON_CLIPS = os.environ.get(
    "VIDEO_STRIP_AUDIO_ON_CLIPS", "true"
).lower() in ("1", "true", "yes")

# ffmpeg on NAS / iPhone MOV can be slow; timeouts skip a segment instead of failing the job
FFMPEG_SEGMENT_TIMEOUT_SEC = int(os.environ.get("FFMPEG_SEGMENT_TIMEOUT_SEC", "1800"))
FFMPEG_FRAME_TIMEOUT_SEC = int(os.environ.get("FFMPEG_FRAME_TIMEOUT_SEC", "300"))
FFPROBE_TIMEOUT_SEC = int(os.environ.get("FFPROBE_TIMEOUT_SEC", "120"))
FFMPEG_CLIP_TRY_COPY = os.environ.get("FFMPEG_CLIP_TRY_COPY", "true").lower() in (
    "1",
    "true",
    "yes",
)

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

EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "jinaai/jina-embeddings-v5-omni-small"
)

_dims = os.environ.get("EMBEDDING_TRUNCATE_DIM", "").strip()
EMBEDDING_OUTPUT_DIMENSIONALITY: int | None = (
    int(_dims) if _dims.isdigit() else None
)


def ensure_output_dirs() -> None:
    for d in (
        MANIFESTS_DIR,
        JOBS_DIR,
        THUMBNAILS_DIR,
        FRAMES_DIR,
        CLIPS_DIR,
        EMBEDDINGS_DIR,
        METADATA_DIR,
        LOGS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
