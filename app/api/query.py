"""Semantic search over a completed job."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from app.api.deps import DbDep, SettingsDep
from app.api.schemas import QueryHit, QueryRequest
from app.db.models import Asset, EmbedTarget, Embedding, Job
from multimodal_memory.embed import embed_text

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=list[QueryHit])
def semantic_query(body: QueryRequest, db: DbDep, settings: SettingsDep) -> list[QueryHit]:
    job_id = body.job_id
    if job_id is None:
        job_id = db.scalar(
            select(Job.id)
            .where(Job.status == "completed")
            .order_by(Job.updated_at.desc())
            .limit(1)
        )
    if job_id is None:
        raise HTTPException(
            status_code=400,
            detail="No completed job found; pass job_id explicitly.",
        )

    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed yet")

    qvec = embed_text(
        body.text,
        task_type="query",
        truncate_dim=settings.embedding_truncate_dim,
    )

    dist_expr = Embedding.vector.cosine_distance(qvec)
    stmt = (
        select(EmbedTarget, Embedding, dist_expr.label("dist"))
        .join(Embedding, EmbedTarget.id == Embedding.embed_target_id)
        .where(EmbedTarget.job_id == job_id)
        .order_by(dist_expr)
        .limit(body.top_k)
    )
    rows = db.execute(stmt).all()

    hits: list[QueryHit] = []
    for et, _emb, dist in rows:
        thumb_url = None
        clip_url = None
        asset = db.scalar(
            select(Asset).where(
                Asset.job_id == job_id,
                Asset.external_key == et.asset_external_key,
            )
        )
        if et.modality == "video":
            clip_url = f"/api/jobs/{job_id}/media/clip/{et.id}"
        if asset and asset.thumbnail_path:
            thumb_url = f"/api/jobs/{job_id}/media/thumbnail/{asset.id}"

        d = float(dist)
        score = 1.0 / (1.0 + d)
        hits.append(
            QueryHit(
                embed_target_id=et.id,
                asset_external_key=et.asset_external_key,
                modality=et.modality,
                source_path=et.source_path,
                path_embedded=et.path,
                mime_type=et.mime_type,
                t_start_sec=et.t_start_sec,
                t_end_sec=et.t_end_sec,
                whole_source_file=et.whole_source_file,
                distance=d,
                score=score,
                thumbnail_url=thumb_url,
                clip_url=clip_url,
            )
        )
    return hits
