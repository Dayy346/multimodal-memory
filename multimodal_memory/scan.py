"""Scan directories for image and video files."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from config.settings import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS


def file_kind(suffix: str) -> str | None:
    lower = suffix.lower()
    if lower in IMAGE_EXTENSIONS:
        return "image"
    if lower in VIDEO_EXTENSIONS:
        return "video"
    return None


def stable_asset_id(abs_path: str) -> str:
    return hashlib.sha256(abs_path.encode("utf-8")).hexdigest()[:16]


def iter_media_files(roots: list[Path], max_files: int | None) -> list[dict]:
    rows: list[dict] = []
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            kind = file_kind(path.suffix)
            if kind is None:
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            abs_s = str(path)
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                rel = abs_s
            rows.append(
                {
                    "id": stable_asset_id(abs_s),
                    "kind": kind,
                    "path": abs_s,
                    "rel_path": rel,
                    "bytes": st.st_size,
                    "mtime_unix": int(st.st_mtime),
                }
            )
            if max_files is not None and len(rows) >= max_files:
                return rows
    rows.sort(key=lambda r: r["path"])
    return rows


def write_manifest_jsonl(
    rows: list[dict],
    output: Path,
    *,
    built_at: str | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    ts = built_at or datetime.now(timezone.utc).isoformat()
    with output.open("w", encoding="utf-8") as f:
        for row in rows:
            out = {**row, "manifest_built_at": ts}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
