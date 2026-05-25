"""Build JobOut with computed progress fields."""

from __future__ import annotations

from app.api.schemas import JobOut
from app.db.models import Job
from app.services.job_progress import compute_job_progress


def job_to_out(job: Job) -> JobOut:
    pct, label, step_id = compute_job_progress(job)
    return JobOut(
        id=job.id,
        status=job.status,
        step=job.step,
        message=job.message,
        error=job.error,
        scan_root=job.scan_root,
        subpath=job.subpath,
        options=job.options or {},
        logs=job.logs or [],
        created_at=job.created_at,
        updated_at=job.updated_at,
        progress_percent=pct,
        progress_label=label,
        progress_step=step_id,
    )
