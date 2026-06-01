"""Allowed scan roots (server-side allowlist)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SettingsDep
from app.api.schemas import RootEntry

router = APIRouter(prefix="/roots", tags=["roots"])


@router.get("", response_model=list[RootEntry])
def list_roots(settings: SettingsDep) -> list[RootEntry]:
    roots = settings.roots_list()
    return [RootEntry(index=i, path=str(p)) for i, p in enumerate(roots)]
