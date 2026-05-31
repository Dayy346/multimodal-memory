"""Indexing jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DbDep, SettingsDep
from app.api.job_out import job_to_out
from app.api.schemas import JobCreate, JobExtend, JobOut, JobResume, JobSummary
from app.db.models import Asset, EmbedTarget, Embedding, Job
from app.services.job_extend import assert_job_extendable, job_vector_count, run_extend_job
from app.services.job_resume import assert_job_resumable, run_resume_job
from app.services.job_runner import run_index_job
from app.services.paths import resolve_scan_directory

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("", response_model=list[JobOut])
def list_jobs(db: DbDep, limit: int = 50) -> list[JobOut]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200))
    return [job_to_out(j) for j in db.scalars(stmt).all()]


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    body: JobCreate,
    db: DbDep,
    settings: SettingsDep,
    tasks: BackgroundTasks,
) -> JobOut:
    try:
        scan_dir = resolve_scan_directory(settings, body.root_index, body.subpath)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    raw_opts = {
        "max_files": body.max_files,
        "max_videos": body.max_videos,
        "max_embed_targets": body.max_embed_targets,
        "chunk_seconds": body.chunk_seconds,
        "thumb_max": body.thumb_max,
        "video_poster": body.video_poster,
        "fallback_frames": body.fallback_frames,
        "skip_thumbnails": body.skip_thumbnails,
    }
    opts = {k: v for k, v in raw_opts.items() if v is not None}
    job = Job(
        status="pending",
        step="queued",
        message="Waiting for worker",
        scan_root=str(scan_dir),
        subpath=body.subpath,
        options=opts,
    )
    job.created_at = _utcnow()
    job.updated_at = _utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    tasks.add_task(run_index_job, job.id)
    return job_to_out(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: DbDep) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_out(job)


@router.get("/{job_id}/summary", response_model=JobSummary)
def get_job_summary(job_id: uuid.UUID, db: DbDep) -> JobSummary:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    assets = int(
        db.scalar(select(func.count()).select_from(Asset).where(Asset.job_id == job_id))
        or 0
    )
    targets = int(
        db.scalar(
            select(func.count()).select_from(EmbedTarget).where(EmbedTarget.job_id == job_id)
        )
        or 0
    )
    return JobSummary(
        job_id=job.id,
        status=job.status,
        scan_root=job.scan_root,
        vector_count=job_vector_count(db, job_id),
        embed_target_count=targets,
        asset_count=assets,
    )


@router.post("/{job_id}/extend", response_model=JobOut)
def extend_job(
    job_id: uuid.UUID,
    body: JobExtend,
    db: DbDep,
    tasks: BackgroundTasks,
) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        assert_job_extendable(job)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    prior = dict(job.options or {})
    raw = {
        "max_files": body.max_files,
        "max_videos": body.max_videos,
        "max_new_embed_targets": body.max_new_embed_targets,
        "chunk_seconds": body.chunk_seconds,
        "thumb_max": body.thumb_max,
        "video_poster": body.video_poster,
        "fallback_frames": body.fallback_frames,
        "skip_thumbnails": body.skip_thumbnails,
    }
    for k, v in raw.items():
        if v is not None:
            prior[k] = v
    if prior.get("skip_thumbnails") is None:
        prior["skip_thumbnails"] = True
    job.options = prior
    job.status = "pending"
    job.step = "extend_queued"
    job.message = "Queued: add new vectors (skip duplicates)"
    job.error = None
    job.updated_at = _utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    tasks.add_task(run_extend_job, job.id)
    return job_to_out(job)


@router.post("/{job_id}/resume", response_model=JobOut)
def resume_job(
    job_id: uuid.UUID,
    body: JobResume,
    db: DbDep,
    tasks: BackgroundTasks,
) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        assert_job_resumable(job)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    prior = dict(job.options or {})
    if body.max_new_embed_targets is not None:
        prior["max_new_embed_targets"] = body.max_new_embed_targets
    prior["skip_preprocess"] = body.skip_preprocess
    job.options = prior
    job.status = "pending"
    job.step = "resume_queued"
    job.message = "Queued: continue embedding (skip duplicates)"
    job.error = None
    job.updated_at = _utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    tasks.add_task(run_resume_job, job.id)
    return job_to_out(job)
