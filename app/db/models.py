"""ORM models for jobs, assets, embed targets, and embeddings."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_EMB_DIM = int(os.environ.get("EMBEDDING_VECTOR_DIM", "3072"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")
    step: Mapped[str] = mapped_column(String(64), default="queued")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_root: Mapped[str] = mapped_column(Text)
    subpath: Mapped[str] = mapped_column(Text, default="")
    options: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    logs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    assets: Mapped[list["Asset"]] = relationship(back_populates="job")
    embed_targets: Mapped[list["EmbedTarget"]] = relationship(back_populates="job")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    external_key: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    source_path: Mapped[str] = mapped_column(Text)
    bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    mtime_unix: Mapped[int] = mapped_column(Integer, default=0)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="assets")


class EmbedTarget(Base):
    __tablename__ = "embed_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    asset_external_key: Mapped[str] = mapped_column(String(32), index=True)
    embed_id: Mapped[str] = mapped_column(String(64), index=True)
    modality: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(128))
    source_path: Mapped[str] = mapped_column(Text)
    t_start_sec: Mapped[float | None] = mapped_column(nullable=True)
    t_end_sec: Mapped[float | None] = mapped_column(nullable=True)
    whole_source_file: Mapped[bool] = mapped_column(Boolean, default=False)

    job: Mapped["Job"] = relationship(back_populates="embed_targets")
    embedding: Mapped["Embedding | None"] = relationship(
        back_populates="embed_target", uselist=False
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    embed_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("embed_targets.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(128))
    dims: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float]] = mapped_column(Vector(_EMB_DIM))

    embed_target: Mapped["EmbedTarget"] = relationship(back_populates="embedding")
