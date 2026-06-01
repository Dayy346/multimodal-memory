"""Resume embedding for a job — skips scan/preprocess when manifests already exist."""

from __future__ import annotations

import json
import traceback
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import EmbedTarget, Job
from app.db.session import SessionLocal
from config.settings import JOBS_DIR
from multimodal_memory.embed import embed_bytes, get_client
from multimodal_memory.images import load_embed_payload
from multimodal_memory.preprocess import (
    build_embed_manifest_fast,
    read_embed_manifest_jsonl,
    run_preprocess,
)
from multimodal_memory.scan import iter_media_files, write_manifest_jsonl

from app.services.job_extend import job_vector_count
from app.services.job_runner import _append_log, _expected_dim, _utcnow

_BUSY = frozenset({"pending", "scanning", "preprocessing", "embedding"})


def assert_job_resumable(job: Job) -> None:
    if (job.status or "").lower() in _BUSY:
        raise ValueError("Job is already running; wait for it to finish")


def _sync_thumbnails_from_artifacts(db, job: Job, artifact_path: Path) -> None:
    if not artifact_path.is_file():
        return
    from sqlalchemy import update

    from app.db.models import Asset

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


def _embed_rows(
    db,
    job: Job,
    *,
    rows: list[dict],
    existing_embed_ids: set[str],
    max_count: int,
    had_vectors: int,
) -> int:
    settings = get_settings()
    expected_dim = _expected_dim()
    client = get_client()
    model = settings.gemini_embedding_model
    dims_opt = settings.gemini_embedding_dimensionality

    pending = [
        er
        for er in rows
        if str(er.get("embed_id") or "") not in existing_embed_ids
    ]
    skipped = len(rows) - len(pending)
    if skipped:
        _append_log(db, job, f"Skipped {skipped} already indexed (duplicate embed_id)")

    if len(pending) > max_count:
        pending = pending[:max_count]
        _append_log(db, job, f"Capped embed targets to {max_count} this run")

    if not pending:
        return 0

    _append_log(db, job, f"Prepared {len(pending)} embed targets")

    job.status = "embedding"
    job.step = "embed"
    job.message = "Resume: calling Gemini embedding API"
    job.updated_at = _utcnow()
    db.add(job)
    db.commit()

    done = 0
    total = len(pending)
    for er in pending:
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

        from app.db.models import Embedding

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
        job.message = f"Embedding {done}/{total} ({had_vectors} existing)"
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()
        log_every = 1 if total <= 30 else 5
        if done % log_every == 0 or done == total:
            _append_log(db, job, f"Embedded {done}/{total}")

    return done


def run_resume_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return

        opts = dict(job.options or {})
        max_embed = int(
            opts.get("max_new_embed_targets")
            or opts.get("max_embed_targets")
            or 200
        )
        skip_preprocess = bool(opts.get("skip_preprocess", False))

        existing_embed_ids = set(
            db.scalars(
                select(EmbedTarget.embed_id).where(EmbedTarget.job_id == job_id)
            ).all()
        )
        had_vectors = len(existing_embed_ids)

        job_dir = JOBS_DIR / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = job_dir / "media_manifest.jsonl"
        embed_manifest_path = job_dir / "embed_manifest.jsonl"
        artifact_path = job_dir / "preprocess_artifacts.jsonl"
        thumbs_dir = job_dir / "thumbnails"
        frames_dir = job_dir / "frames"
        clips_dir = job_dir / "clips"

        job.error = None
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

        if not skip_preprocess or not embed_manifest_path.is_file():
            if not manifest_path.is_file() or not skip_preprocess:
                scan_path = Path(job.scan_root)
                job.status = "scanning"
                job.step = "scan"
                job.message = f"Resume: scanning {scan_path}"
                db.add(job)
                db.commit()

                max_files = int(opts.get("max_files") or 500)
                rows = iter_media_files([scan_path], max_files)
                write_manifest_jsonl(rows, manifest_path)
                _append_log(db, job, f"Found {len(rows)} media files")

            if not skip_preprocess or not embed_manifest_path.is_file():
                job.status = "preprocessing"
                job.step = "preprocess"
                job.message = "Resume: building embed manifest"
                db.add(job)
                db.commit()

                max_videos = opts.get("max_videos")
                max_videos_i = int(max_videos) if max_videos is not None else None
                chunk_seconds = opts.get("chunk_seconds")
                chunk_f = float(chunk_seconds) if chunk_seconds is not None else None
                fallback_frames = int(opts.get("fallback_frames") or 0)
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
                _sync_thumbnails_from_artifacts(db, job, artifact_path)
        else:
            _append_log(db, job, "Skipped scan/preprocess — using existing embed manifest")

        manifest_lines = 0
        if embed_manifest_path.is_file():
            manifest_lines = len(read_embed_manifest_jsonl(embed_manifest_path))
        if manifest_lines < had_vectors // 2 and had_vectors > 50:
            if not manifest_path.is_file():
                scan_path = Path(job.scan_root)
                max_files = int(opts.get("max_files") or 500)
                rows = iter_media_files([scan_path], max_files)
                write_manifest_jsonl(rows, manifest_path)
            max_videos = opts.get("max_videos")
            max_videos_i = int(max_videos) if max_videos is not None else None
            _append_log(
                db,
                job,
                f"Embed manifest incomplete ({manifest_lines} lines) — rebuilding fast",
            )
            built = build_embed_manifest_fast(
                manifest_path,
                embed_manifest_path,
                skip_videos=max_videos_i is None or max_videos_i <= 0,
            )
            _append_log(db, job, f"Fast manifest rebuilt with {built} image targets")

        all_rows = read_embed_manifest_jsonl(embed_manifest_path)
        done = _embed_rows(
            db,
            job,
            rows=all_rows,
            existing_embed_ids=existing_embed_ids,
            max_count=max_embed,
            had_vectors=had_vectors,
        )

        total = job_vector_count(db, job_id)
        if done == 0:
            job.status = "completed"
            job.step = "done"
            job.message = f"No new vectors to add ({total} total)"
            _append_log(db, job, "Resume finished — nothing new to embed")
        else:
            job.status = "completed"
            job.step = "done"
            job.message = f"Added {done} vectors ({total} total, was {had_vectors})"
            _append_log(db, job, "Resume completed")
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

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
