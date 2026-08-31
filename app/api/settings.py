"""App settings (local embedding model status)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import EmbeddingStatus
from multimodal_memory.embed import ensure_model_loaded, model_status

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/embedding", response_model=EmbeddingStatus)
def get_embedding_status() -> EmbeddingStatus:
    return EmbeddingStatus(**model_status())


@router.post("/embedding/load", response_model=EmbeddingStatus)
def load_embedding_model() -> EmbeddingStatus:
    try:
        status = ensure_model_loaded()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return EmbeddingStatus(**status)
