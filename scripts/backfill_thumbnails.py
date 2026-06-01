"""Regenerate thumbnails for assets in an existing job (e.g. HEIC after pillow-heif)."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.db.models import Asset, Job
from app.db.session import SessionLocal
from config.settings import JOBS_DIR
from multimodal_memory.images import HEIF_EXTENSIONS, write_thumbnail_jpeg
from multimodal_memory.preprocess import safe_stem


def _load_dotenv() -> None:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", type=uuid.UUID, required=True)
    parser.add_argument(
        "--heic-only",
        action="store_true",
        help="Only sources ending in .heic / .heif",
    )
    parser.add_argument(
        "--all-images",
        action="store_true",
        help="Include all image assets (default: missing/broken thumb only)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when thumbnail file already exists",
    )
    parser.add_argument("--thumb-max", type=int, default=512)
    args = parser.parse_args()

    job_id = args.job_id
    thumbs_dir = JOBS_DIR / str(job_id) / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            print(f"Job not found: {job_id}")
            sys.exit(1)

        assets = list(
            db.scalars(select(Asset).where(Asset.job_id == job_id, Asset.kind == "image"))
        )
        print(f"Job {job_id} — {len(assets)} image assets")

        built = 0
        skipped = 0
        failed = 0

        for asset in assets:
            src = Path(asset.source_path)
            if not src.is_file():
                skipped += 1
                continue
            if args.heic_only and src.suffix.lower() not in HEIF_EXTENSIONS:
                skipped += 1
                continue

            dest = thumbs_dir / f"{asset.external_key}_{safe_stem(src.stem)}.jpg"
            thumb_ok = dest.is_file() and dest.stat().st_size > 0
            if not args.force and not args.all_images:
                if asset.thumbnail_path and Path(asset.thumbnail_path).is_file():
                    db_path = Path(asset.thumbnail_path)
                    if db_path.stat().st_size > 0:
                        skipped += 1
                        continue
                if thumb_ok:
                    asset.thumbnail_path = str(dest.resolve())
                    built += 1
                    continue

            if args.force or not thumb_ok:
                if not write_thumbnail_jpeg(src, dest, args.thumb_max):
                    failed += 1
                    continue

            if dest.is_file():
                asset.thumbnail_path = str(dest.resolve())
                built += 1
            else:
                failed += 1

        db.commit()
        print(f"Thumbnails ready: {built}  skipped: {skipped}  failed: {failed}")
        print(f"Output: {thumbs_dir}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
