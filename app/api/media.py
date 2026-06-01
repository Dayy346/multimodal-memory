"""Serve thumbnails and clip files for a job (safe path checks)."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import DbDep
from app.db.models import Asset, EmbedTarget, Job
from config.settings import JOBS_DIR

router = APIRouter(prefix="/jobs/{job_id}/media", tags=["media"])


def _job_dir(job_id: uuid.UUID) -> Path:
    return (JOBS_DIR / str(job_id)).resolve()


def _resolved_clip_path(job_id: uuid.UUID, et: EmbedTarget) -> Path:
    job_root = _job_dir(job_id)
    target = Path(et.path).resolve()
    if et.whole_source_file:
        src = Path(et.source_path).resolve()
        if target == src and target.is_file():
            return target
        raise HTTPException(status_code=403, detail="Whole-file path mismatch")
    try:
        target.relative_to(job_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Clip outside job directory") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Clip missing on disk")
    return target


def _resolved_thumb_path(job_id: uuid.UUID, asset: Asset) -> Path:
    job_root = _job_dir(job_id)
    if not asset.thumbnail_path:
        raise HTTPException(status_code=404, detail="No thumbnail for this asset")
    target = Path(asset.thumbnail_path).resolve()
    try:
        target.relative_to(job_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Thumbnail outside job directory") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail missing on disk")
    return target


@router.get("/thumbnail/{asset_id}")
def serve_thumbnail(job_id: uuid.UUID, asset_id: uuid.UUID, db: DbDep) -> FileResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    asset = db.get(Asset, asset_id)
    if asset is None or asset.job_id != job_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = _resolved_thumb_path(job_id, asset)
    mt = "image/jpeg"
    if path.suffix.lower() in {".png"}:
        mt = "image/png"
    return FileResponse(path, media_type=mt, filename=path.name)


@router.get("/clip/{embed_target_id}")
def serve_clip(
    job_id: uuid.UUID,
    embed_target_id: uuid.UUID,
    db: DbDep,
) -> FileResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    et = db.scalar(
        select(EmbedTarget).where(
            EmbedTarget.id == embed_target_id,
            EmbedTarget.job_id == job_id,
        )
    )
    if et is None:
        raise HTTPException(status_code=404, detail="Embed target not found")
    path = _resolved_clip_path(job_id, et)
    return FileResponse(path, media_type=et.mime_type, filename=path.name)
