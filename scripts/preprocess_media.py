"""Prepare embed targets: original images, video clips, thumbnails."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (  # noqa: E402
    EMBED_MANIFEST_NAME,
    METADATA_DIR,
    VIDEO_EMBED_MAX_SECONDS,
    ensure_output_dirs,
)
from multimodal_memory.preprocess import run_preprocess  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="JSONL manifest from build_manifest.py",
    )
    parser.add_argument(
        "--thumb-max",
        type=int,
        default=512,
        help="Longest side for image thumbnails (pixels).",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=float,
        default=None,
        help=(
            "Max length of each derived video clip for embedding "
            f"(default: {VIDEO_EMBED_MAX_SECONDS} from env VIDEO_EMBED_MAX_SECONDS)."
        ),
    )
    parser.add_argument(
        "--video-poster",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Save one JPEG poster per video under thumbnails (for you, not sent to embed).",
    )
    parser.add_argument(
        "--fallback-frames",
        type=int,
        default=0,
        help=(
            "If ffmpeg is missing, sample this many frames per video and embed those "
            "JPEGs instead (worse than real video clips)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite thumbnails, posters, and derived clips.",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=None,
        help="Process at most this many video sources (cost control).",
    )
    args = parser.parse_args()
    ensure_output_dirs()
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    embed_manifest_path = METADATA_DIR / EMBED_MANIFEST_NAME
    artifact_path = METADATA_DIR / "preprocess_artifacts.jsonl"

    stats = run_preprocess(
        args.manifest,
        embed_manifest_path=embed_manifest_path,
        artifact_path=artifact_path,
        thumb_max=args.thumb_max,
        chunk_seconds=args.chunk_seconds,
        video_poster=args.video_poster,
        fallback_frames=args.fallback_frames,
        force=args.force,
        max_videos=args.max_videos,
    )
    print(f"Wrote embed targets: {stats['embed_manifest_path']}")
    print(f"Wrote artifact index: {stats['artifact_path']}")


if __name__ == "__main__":
    main()
