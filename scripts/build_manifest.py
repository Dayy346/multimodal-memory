"""Walk scan roots and write a JSONL manifest of image and video files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import MANIFESTS_DIR, ensure_output_dirs  # noqa: E402
from multimodal_memory.scan import iter_media_files, write_manifest_jsonl  # noqa: E402


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

    rows = iter_media_files(roots, args.limit)
    write_manifest_jsonl(rows, args.output)
    print(f"Wrote {len(rows)} entries to {args.output}")


if __name__ == "__main__":
    main()
