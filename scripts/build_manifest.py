"""Walk scan roots and write a JSONL manifest of image and video files."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (  # noqa: E402
    IMAGE_EXTENSIONS,
    MANIFESTS_DIR,
    VIDEO_EXTENSIONS,
    ensure_output_dirs,
)


def _file_kind(suffix: str) -> str | None:
    lower = suffix.lower()
    if lower in IMAGE_EXTENSIONS:
        return "image"
    if lower in VIDEO_EXTENSIONS:
        return "video"
    return None


def _stable_id(abs_path: str) -> str:
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
            kind = _file_kind(path.suffix)
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
                    "id": _stable_id(abs_s),
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scan",
        action="append",
        required=True,
        help="Directory to scan (repeatable).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MANIFESTS_DIR / "media_manifest.jsonl",
        help="JSONL output path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many media files (debug).",
    )
    args = parser.parse_args()
    roots = [Path(p).expanduser() for p in args.scan]
    ensure_output_dirs()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    built_at = datetime.now(timezone.utc).isoformat()
    rows = iter_media_files(roots, args.limit)
    with args.output.open("w", encoding="utf-8") as f:
        for row in rows:
            row["manifest_built_at"] = built_at
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} entries to {args.output}")


if __name__ == "__main__":
    main()
