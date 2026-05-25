"""Pydantic request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RootEntry(BaseModel):
    index: int
    path: str


class JobCreate(BaseModel):
    root_index: int = Field(ge=0)
    subpath: str = ""
    max_files: int | None = Field(default=500, ge=1, le=500_000)
    max_videos: int | None = None
    max_embed_targets: int | None = Field(default=200, ge=1, le=50_000)
    chunk_seconds: float | None = None
    thumb_max: int = Field(default=512, ge=64, le=4096)
    video_poster: bool = True
    fallback_frames: int = Field(default=0, ge=0, le=30)

    @field_validator("chunk_seconds")
    @classmethod
    def chunk_seconds_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("chunk_seconds must be > 0 when set")
        return v

    @field_validator("max_videos")
    @classmethod
    def max_videos_positive(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("max_videos must be >= 1 when set")
        return v


class JobOut(BaseModel):
    id: uuid.UUID
    status: str
    step: str
    message: str | None
    error: str | None
    scan_root: str
    subpath: str
    options: dict[str, Any]
    logs: list[Any]
    created_at: datetime
    updated_at: datetime
    progress_percent: int = 0
    progress_label: str = ""
    progress_step: str = "queued"

    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    job_id: uuid.UUID | None = None
    text: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=12, ge=1, le=100)


class QueryHit(BaseModel):
    embed_target_id: uuid.UUID
    asset_external_key: str
    modality: str
    source_path: str
    path_embedded: str
    mime_type: str
    t_start_sec: float | None
    t_end_sec: float | None
    whole_source_file: bool
    distance: float
    score: float
    thumbnail_url: str | None
    clip_url: str | None
