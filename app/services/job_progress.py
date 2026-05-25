"""Derive indexing progress percent and label from job state and logs."""

from __future__ import annotations

import re
from typing import Any

from app.db.models import Job

_FOUND_RE = re.compile(r"Found (\d+) media files")
_PREPARED_RE = re.compile(r"Prepared (\d+) embed targets")
_EMBED_RE = re.compile(r"Embedded (\d+)/(\d+)")
_EMBED_NEW_RE = re.compile(r"Embedded new (\d+)/(\d+)")


def _log_strings(logs: list[Any] | None) -> list[str]:
    if not logs:
        return []
    out: list[str] = []
    for entry in logs:
        if isinstance(entry, str):
            out.append(entry)
        else:
            out.append(str(entry))
    return out


def compute_job_progress(job: Job) -> tuple[int, str, str]:
    """Return (percent 0–100, label, active_step_id)."""
    status = (job.status or "").lower()
    step = (job.step or "").lower()
    logs = _log_strings(job.logs)
    opts = job.options or {}

    if status == "completed":
        return 100, job.message or "Indexing complete", "done"

    if status == "failed":
        return 0, "Job failed", "error"

    found_n: int | None = None
    prepared_n: int | None = None
    embed_done = 0
    embed_total = 0
    for line in logs:
        m = _FOUND_RE.search(line)
        if m:
            found_n = int(m.group(1))
        m = _PREPARED_RE.search(line)
        if m:
            prepared_n = int(m.group(1))
        m = _EMBED_NEW_RE.search(line)
        if m:
            embed_done = int(m.group(1))
            embed_total = int(m.group(2))
        else:
            m = _EMBED_RE.search(line)
            if m:
                embed_done = int(m.group(1))
                embed_total = int(m.group(2))

    max_embed = int(
        opts.get("max_new_embed_targets") or opts.get("max_embed_targets") or 200
    )

    if status in ("pending",) or step in ("queued", "extend_queued"):
        return 2, job.message or "Waiting to start…", "queued"

    if status == "scanning" or step == "scan":
        if found_n is not None:
            return 18, f"Found {found_n} files", "scan"
        return 10, job.message or "Scanning folder…", "scan"

    if status == "preprocessing" or step == "preprocess":
        label = job.message or "Thumbnails and video clips…"
        if prepared_n is not None:
            return 40, f"Prepared {prepared_n} embed targets", "preprocess"
        if found_n is not None:
            return 32, label, "preprocess"
        return 28, label, "preprocess"

    if status == "embedding" or step == "embed":
        total = embed_total or prepared_n or max_embed
        if total > 0 and embed_done > 0:
            pct = 42 + round(53 * min(embed_done / total, 1.0))
            return min(pct, 99), f"Embedding {embed_done} / {total}", "embed"
        return 45, job.message or "Starting embeddings…", "embed"

    return 5, job.message or status or "Working…", step or "queued"
