"""Append embeddings to an existing job, skipping duplicate embed_id values."""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.db.models import Asset, EmbedTarget, Embedding, Job
from app.db.session import SessionLocal
from config.settings import JOBS_DIR
from multimodal_memory.embed import embed_bytes, get_client
from multimodal_memory.images import load_embed_payload
from multimodal_memory.preprocess import read_embed_manifest_jsonl, run_preprocess
from multimodal_memory.scan import iter_media_files, write_manifest_jsonl

from app.services.job_runner import _append_log, _expected_dim, _utcnow

_BUSY = frozenset({"pending", "scanning", "preprocessing", "embedding"})


def job_vector_count(db, job_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Embedding)
            .join(EmbedTarget, EmbedTarget.id == Embedding.embed_target_id)
            .where(EmbedTarget.job_id == job_id)
        )
        or 0
    )


def run_extend_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    settings = get_settings()
    expected_dim = _expected_dim()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return

        opts = dict(job.options or {})
        max_files = int(opts.get("max_files") or 10_000)
        max_videos = opts.get("max_videos")
        max_videos_i = int(max_videos) if max_videos is not None else None
        max_new = int(opts.get("max_new_embed_targets") or 200)
        chunk_seconds = opts.get("chunk_seconds")
        chunk_f = float(chunk_seconds) if chunk_seconds is not None else None
        fallback_frames = int(opts.get("fallback_frames") or 0)

        existing_embed_ids = set(
            db.scalars(
                select(EmbedTarget.embed_id).where(EmbedTarget.job_id == job_id)
            ).all()
        )
        had_vectors = len(existing_embed_ids)

        job_dir = JOBS_DIR / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir = job_dir / "thumbnails"
        frames_dir = job_dir / "frames"
        clips_dir = job_dir / "clips"
        manifest_path = job_dir / "media_manifest.jsonl"
        embed_manifest_path = job_dir / "embed_manifest.jsonl"
        artifact_path = job_dir / "preprocess_artifacts.jsonl"

        scan_path = Path(job.scan_root)
        job.status = "scanning"
        job.step = "scan"
        job.message = f"Extend: scanning {scan_path}"
        job.error = None
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

        rows = iter_media_files([scan_path], max_files)
        write_manifest_jsonl(rows, manifest_path)
        _append_log(db, job, f"Found {len(rows)} media files")

        existing_asset_keys = set(
            db.scalars(
                select(Asset.external_key).where(Asset.job_id == job_id)
            ).all()
        )
        new_assets = 0
        for row in rows:
            if row["id"] in existing_asset_keys:
                continue
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
            new_assets += 1
        db.commit()
        _append_log(db, job, f"Added {new_assets} new assets to catalog")

        job.status = "preprocessing"
        job.step = "preprocess"
        job.message = "Extend: thumbnails and clips"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

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

        all_rows = read_embed_manifest_jsonl(embed_manifest_path)
        new_rows = [
            er
            for er in all_rows
            if str(er.get("embed_id") or "") not in existing_embed_ids
        ]
        skipped = len(all_rows) - len(new_rows)
        _append_log(db, job, f"Skipped {skipped} already indexed (duplicate embed_id)")

        if len(new_rows) > max_new:
            new_rows = new_rows[:max_new]
            _append_log(db, job, f"Capped new embed targets to {max_new} this run")

        _append_log(db, job, f"Prepared {len(new_rows)} new embed targets")

        job.status = "embedding"
        job.step = "embed"
        job.message = "Extend: calling Gemini embedding API"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

        if not new_rows:
            total = job_vector_count(db, job_id)
            job.status = "completed"
            job.step = "done"
            job.message = f"No new vectors to add ({total} total)"
            job.updated_at = _utcnow()
            db.add(job)
            db.commit()
            _append_log(db, job, "Extend finished — nothing new")
            return

        client = get_client()
        model = settings.gemini_embedding_model
        dims_opt = settings.gemini_embedding_dimensionality

        done = 0
        total_new = len(new_rows)
        for er in new_rows:
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

            if et.modality == "image":
                data, embed_mime = load_embed_payload(p)
            else:
                data = p.read_bytes()
                embed_mime = et.mime_type

            vec = embed_bytes(
                client,
                model,
                data,
                embed_mime,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=dims_opt,
            )
            if len(vec) != expected_dim:
                raise RuntimeError(
                    f"Embedding length {len(vec)} != EMBEDDING_VECTOR_DIM {expected_dim}"
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
            job.message = f"Embedding new {done}/{total_new} ({had_vectors} existing)"
            job.updated_at = _utcnow()
            db.add(job)
            db.commit()
            log_every = 1 if total_new <= 30 else 5
            if done % log_every == 0 or done == total_new:
                _append_log(db, job, f"Embedded new {done}/{total_new}")

        total = job_vector_count(db, job_id)
        job.status = "completed"
        job.step = "done"
        job.message = f"Added {done} vectors ({total} total, was {had_vectors})"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()
        _append_log(db, job, "Extend completed")

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


def assert_job_extendable(job: Job) -> None:
    if (job.status or "").lower() in _BUSY:
        raise ValueError("Job is already running; wait for it to finish")
