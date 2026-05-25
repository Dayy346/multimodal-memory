"""HEIC/HEIF and raster image helpers (thumbnails + embedding payloads)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

_HEIF_REGISTERED = False

HEIF_EXTENSIONS = frozenset({".heic", ".heif"})


def register_heif_opener() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        _HEIF_REGISTERED = True
    except ImportError:
        pass


def is_heif_path(path: Path) -> bool:
    return path.suffix.lower() in HEIF_EXTENSIONS


def open_image(path: Path) -> Image.Image:
    register_heif_opener()
    return Image.open(path)


def write_thumbnail_jpeg(src: Path, dest: Path, max_side: int) -> bool:
    try:
        with open_image(src) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            im.save(dest, "JPEG", quality=88, optimize=True)
    except OSError:
        return False
    return dest.is_file()


def load_embed_payload(path: Path) -> tuple[bytes, str]:
    # Gemini embedding is reliable with JPEG/PNG; transcode HEIC/HEIF first.
    if is_heif_path(path):
        register_heif_opener()
        with open_image(path) as im:
            im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=92, optimize=True)
            return buf.getvalue(), "image/jpeg"
    data = path.read_bytes()
    mime = _mime_for_embed(path)
    return data, mime


def _mime_for_embed(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    if ext in HEIF_EXTENSIONS:
        return "image/heic"
    if ext == ".gif":
        return "image/gif"
    if ext in {".bmp", ".tif", ".tiff"}:
        return "image/jpeg"
    return "application/octet-stream"
