"""Indexing jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbDep, SettingsDep
from app.api.schemas import JobCreate, JobOut
from app.db.models import Job
from app.services.job_runner import run_index_job
from app.services.paths import resolve_scan_directory

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("", response_model=list[JobOut])
def list_jobs(db: DbDep, limit: int = 50) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200))
    return list(db.scalars(stmt).all())


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    body: JobCreate,
    db: DbDep,
    settings: SettingsDep,
    tasks: BackgroundTasks,
) -> Job:
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
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: DbDep) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
