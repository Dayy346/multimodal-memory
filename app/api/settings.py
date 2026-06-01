"""App settings (Gemini API key)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import GeminiKeyStatus, GeminiKeyUpdate
from app.services.gemini_settings import current_api_key, mask_api_key, set_api_key

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/gemini", response_model=GeminiKeyStatus)
def get_gemini_key_status() -> GeminiKeyStatus:
    key = current_api_key()
    if not key:
        return GeminiKeyStatus(configured=False, masked_key=None)
    return GeminiKeyStatus(configured=True, masked_key=mask_api_key(key))


@router.post("/gemini", response_model=GeminiKeyStatus)
def update_gemini_key(body: GeminiKeyUpdate) -> GeminiKeyStatus:
    try:
        set_api_key(body.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    key = current_api_key()
    return GeminiKeyStatus(
        configured=True,
        masked_key=mask_api_key(key) if key else None,
    )
