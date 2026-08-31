"""Background indexing: scan, preprocess, embed, persist to Postgres."""

from __future__ import annotations

import json
import os
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.models import Asset, EmbedTarget, Embedding, Job
from app.db.session import SessionLocal
from config.settings import JOBS_DIR
from multimodal_memory.embed import embed_document_file, ensure_model_loaded
from multimodal_memory.preprocess import read_embed_manifest_jsonl, run_preprocess
from multimodal_memory.scan import iter_media_files, write_manifest_jsonl


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _append_log(db, job: Job, message: str) -> None:
    logs = list(job.logs or [])
    logs.append(message)
    if len(logs) > 500:
        logs = logs[-500:]
    job.logs = logs
    job.updated_at = _utcnow()
    db.add(job)
    db.commit()


def _expected_dim() -> int:
    return int(os.environ.get("EMBEDDING_VECTOR_DIM", "1024"))


def run_index_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    settings = get_settings()
    expected_dim = _expected_dim()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return

        job_dir = JOBS_DIR / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir = job_dir / "thumbnails"
        frames_dir = job_dir / "frames"
        clips_dir = job_dir / "clips"
        manifest_path = job_dir / "media_manifest.jsonl"
        embed_manifest_path = job_dir / "embed_manifest.jsonl"
        artifact_path = job_dir / "preprocess_artifacts.jsonl"

        opts = dict(job.options or {})
        max_files = int(opts.get("max_files") or 500)
        max_videos = opts.get("max_videos")
        max_videos_i = int(max_videos) if max_videos is not None else None
        max_embed = int(opts.get("max_embed_targets") or 200)
        chunk_seconds = opts.get("chunk_seconds")
        chunk_f = float(chunk_seconds) if chunk_seconds is not None else None
        fallback_frames = int(opts.get("fallback_frames") or 0)

        scan_path = Path(job.scan_root)
        job.status = "scanning"
        job.step = "scan"
        job.message = f"Scanning {scan_path}"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

        rows = iter_media_files([scan_path], max_files)
        write_manifest_jsonl(rows, manifest_path)
        _append_log(db, job, f"Found {len(rows)} media files")

        for row in rows:
            db.add(
                Asset(
                    job_id=job.id,
                    external_key=row["id"],
                    kind=row["kind"],
                    source_path=row["path"],
                    bytes=int(row.get("bytes") or 0),
                    mtime_unix=int(row.get("mtime_unix") or 0),
                )
            )
        db.commit()

        job.status = "preprocessing"
        job.step = "preprocess"
        job.message = "Building thumbnails and clips"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

        skip_videos = max_videos_i is not None and max_videos_i <= 0

        def _preprocess_progress(done: int, total: int) -> None:
            job.message = f"Preparing media {done}/{total}"
            job.updated_at = _utcnow()
            db.add(job)
            db.commit()
            if done == 1 or done == total or done % max(1, total // 10) == 0:
                _append_log(db, job, f"Preprocessed {done}/{total} assets")

        run_preprocess(
            manifest_path,
            embed_manifest_path=embed_manifest_path,
            artifact_path=artifact_path,
            thumb_max=int(opts.get("thumb_max") or 512),
            chunk_seconds=chunk_f,
            video_poster=bool(opts.get("video_poster", True)),
            fallback_frames=fallback_frames,
            force=False,
            max_videos=max_videos_i,
            skip_thumbnails=bool(opts.get("skip_thumbnails", False)),
            skip_videos=skip_videos,
            progress_callback=_preprocess_progress,
            use_global_output_dirs=False,
            thumbnails_dir=thumbs_dir,
            frames_dir=frames_dir,
            clips_dir=clips_dir,
        )

        if artifact_path.is_file():
            for line in artifact_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                ext_key = rec.get("id")
                thumb = rec.get("thumbnail_path") or rec.get("poster_path")
                if ext_key and thumb:
                    db.execute(
                        update(Asset)
                        .where(
                            Asset.job_id == job.id,
                            Asset.external_key == ext_key,
                        )
                        .values(thumbnail_path=thumb)
                    )
            db.commit()

        existing_embed_ids = set(
            db.scalars(
                select(EmbedTarget.embed_id).where(EmbedTarget.job_id == job_id)
            ).all()
        )
        all_embed_rows = read_embed_manifest_jsonl(embed_manifest_path)
        embed_rows = [
            er
            for er in all_embed_rows
            if str(er.get("embed_id") or "") not in existing_embed_ids
        ]
        skipped = len(all_embed_rows) - len(embed_rows)
        if skipped:
            _append_log(db, job, f"Skipped {skipped} already indexed (duplicate embed_id)")
        if len(embed_rows) > max_embed:
            embed_rows = embed_rows[:max_embed]
            _append_log(db, job, f"Truncated embed targets to {max_embed}")
        _append_log(db, job, f"Prepared {len(embed_rows)} embed targets")

        job.status = "embedding"
        job.step = "embed"
        job.message = "Loading local embedding model"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()
        ensure_model_loaded()
        _append_log(db, job, f"Embedding with {settings.embedding_model}")

        model = settings.embedding_model
        dims_opt = settings.embedding_truncate_dim

        done = 0
        for er in embed_rows:
            embed_id = str(er.get("embed_id") or "")
            if embed_id in existing_embed_ids:
                continue

            p = Path(str(er.get("path") or ""))
            if not p.is_file():
                _append_log(db, job, f"skip missing embed file: {p}")
                continue

            et = EmbedTarget(
                job_id=job.id,
                asset_external_key=str(er.get("asset_id") or ""),
                embed_id=embed_id,
                modality=str(er.get("modality") or "image"),
                path=str(p.resolve()),
                mime_type=str(er.get("mime_type") or "application/octet-stream"),
                source_path=str(er.get("source_path") or er.get("path") or ""),
                t_start_sec=er.get("t_start_sec"),
                t_end_sec=er.get("t_end_sec"),
                whole_source_file=bool(er.get("whole_source_file", False)),
            )
            db.add(et)
            db.flush()

            vec = embed_document_file(
                p,
                et.modality,
                truncate_dim=dims_opt,
            )
            if len(vec) != expected_dim:
                raise RuntimeError(
                    f"Embedding length {len(vec)} != EMBEDDING_VECTOR_DIM {expected_dim}; "
                    "set EMBEDDING_TRUNCATE_DIM to match or adjust EMBEDDING_VECTOR_DIM."
                )

            db.add(
                Embedding(
                    embed_target_id=et.id,
                    model=model,
                    dims=len(vec),
                    vector=vec,
                )
            )
            db.commit()
            existing_embed_ids.add(embed_id)
            done += 1
            total_embed = len(embed_rows)
            job.message = f"Embedding {done}/{total_embed}"
            job.updated_at = _utcnow()
            db.add(job)
            db.commit()
            log_every = 1 if total_embed <= 30 else 5
            if done % log_every == 0 or done == total_embed:
                _append_log(db, job, f"Embedded {done}/{total_embed}")

        job.status = "completed"
        job.step = "done"
        job.message = f"Indexed {done} embed targets"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()
        _append_log(db, job, "Job completed")

    except Exception:
        err = traceback.format_exc()
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.step = "error"
                job.error = err[-8000:]
                job.updated_at = _utcnow()
                db.add(job)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
