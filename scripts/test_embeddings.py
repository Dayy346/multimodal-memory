"""Embed catalog items from embed_manifest (or legacy globs); rank text queries by similarity."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (  # noqa: E402
    EMBEDDING_OUTPUT_DIMENSIONALITY,
    EMBED_MANIFEST_NAME,
    GEMINI_EMBEDDING_MODEL,
    LOGS_DIR,
    METADATA_DIR,
    ensure_output_dirs,
)
from multimodal_memory.embed import embed_bytes, embed_text, get_client  # noqa: E402
from multimodal_memory.preprocess import read_embed_manifest_jsonl  # noqa: E402


def _load_dotenv() -> None:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _collect_media_paths(globs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in globs:
        paths.extend(PROJECT_ROOT.glob(pattern))
    out = sorted({p.resolve() for p in paths if p.is_file()})
    return out


def _format_segment(row: dict) -> str:
    ts = row.get("t_start_sec")
    te = row.get("t_end_sec")
    if ts is None and te is None:
        return ""
    return f"  segment: {ts}s – {te}s"


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--embed-manifest",
        type=Path,
        default=None,
        help=f"JSONL of embed targets (default: metadata/{EMBED_MANIFEST_NAME}).",
    )
    parser.add_argument(
        "--legacy-glob",
        action="store_true",
        help="Ignore embed manifest; use JPEG globs like the old demo.",
    )
    parser.add_argument(
        "--model",
        default=GEMINI_EMBEDDING_MODEL,
        help="Embedding model id (default from GEMINI_EMBEDDING_MODEL).",
    )
    parser.add_argument(
        "--glob",
        action="append",
        default=[],
        help="With --legacy-glob: glob relative to repo root (repeatable).",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        default=[],
        help="Text query (repeatable).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Matches to print per query.",
    )
    parser.add_argument(
        "--dims",
        type=int,
        default=EMBEDDING_OUTPUT_DIMENSIONALITY,
        help="output_dimensionality (optional; from env if unset).",
    )
    parser.add_argument(
        "--query-task",
        default="RETRIEVAL_QUERY",
        help="task_type for queries (Gemini embed config).",
    )
    parser.add_argument(
        "--media-task",
        default="RETRIEVAL_DOCUMENT",
        help="task_type for catalog items.",
    )
    parser.add_argument(
        "--save-log",
        type=Path,
        default=None,
        help="Write JSON results (default: outputs/logs/embedding_probe.json).",
    )
    args = parser.parse_args()

    dims = args.dims if args.dims else None
    client = get_client()

    catalog: list[dict] = []

    if args.legacy_glob:
        default_globs = ["outputs/thumbnails/**/*.jpg", "outputs/frames/**/*.jpg"]
        globs = args.glob if args.glob else default_globs
        paths = _collect_media_paths(globs)
        if not paths:
            print("No media files matched. Fix --glob or run preprocess_media.py.")
            sys.exit(1)
        for p in paths:
            mime, _ = mimetypes.guess_type(str(p))
            if not mime:
                mime = "image/jpeg"
            catalog.append(
                {
                    "embed_id": str(p),
                    "path": str(p),
                    "mime_type": mime,
                    "source_path": str(p),
                    "modality": "image",
                    "t_start_sec": None,
                    "t_end_sec": None,
                }
            )
    else:
        mpath = args.embed_manifest or (METADATA_DIR / EMBED_MANIFEST_NAME)
        if not mpath.is_file():
            print(
                f"No embed manifest at {mpath}. Run preprocess_media.py first, "
                "or pass --legacy-glob."
            )
            sys.exit(1)
        catalog = read_embed_manifest_jsonl(mpath)

    items: list[tuple[dict, list[float]]] = []
    for row in catalog:
        p = Path(row["path"])
        if not p.is_file():
            print(f"skip missing file: {p}")
            continue
        mime = row.get("mime_type") or mimetypes.guess_type(str(p))[0]
        if not mime:
            mime = "application/octet-stream"
        data = p.read_bytes()
        size_mb = len(data) / (1024 * 1024)
        if size_mb > 80:
            print(f"warning: large payload {size_mb:.1f} MB — {p.name}")
        vec = embed_bytes(
            client,
            args.model,
            data,
            mime,
            task_type=args.media_task,
            output_dimensionality=dims,
        )
        items.append((row, vec))

    if not items:
        print("Nothing to embed (empty catalog or all paths missing).")
        sys.exit(1)

    queries = args.queries or [
        "photos of notes or whiteboards",
        "server hardware racks and cables",
        "gym workout or fitness progress",
        "family gathering or celebration",
    ]

    print(
        f"Model={args.model}  catalog_items={len(items)}  queries={len(queries)}"
    )

    results: dict = {"model": args.model, "queries": []}
    for q in queries:
        qv = embed_text(
            client,
            args.model,
            q,
            task_type=args.query_task,
            output_dimensionality=dims,
        )
        scored = [(row, _cosine(qv, vec)) for row, vec in items]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[: args.top_k]
        block = {
            "query": q,
            "top": [],
        }
        print(f"\nQuery: {q!r}")
        for row, s in top:
            src = row.get("source_path", row["path"])
            seg = _format_segment(row)
            mod = row.get("modality", "?")
            print(f"  {s:.4f}  [{mod}]  source: {src}{seg}")
            print(f"           file_embedded: {row['path']}")
            block["top"].append(
                {
                    "score": s,
                    "modality": mod,
                    "source_path": src,
                    "t_start_sec": row.get("t_start_sec"),
                    "t_end_sec": row.get("t_end_sec"),
                    "path_embedded": row["path"],
                    "embed_id": row.get("embed_id"),
                }
            )
        results["queries"].append(block)

    ensure_output_dirs()
    log_path = args.save_log
    if log_path is None:
        log_path = LOGS_DIR / "embedding_probe.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {log_path}")


if __name__ == "__main__":
    main()
