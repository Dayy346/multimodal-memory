"""Initial schema with pgvector.

Revision ID: 001_initial
Revises:
Create Date: 2026-04-27

"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EMB_DIM = int(os.environ.get("EMBEDDING_VECTOR_DIM", "1024"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("scan_root", sa.Text(), nullable=False),
        sa.Column("subpath", sa.Text(), nullable=False),
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "logs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_key", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("mtime_unix", sa.Integer(), nullable=False),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "external_key", name="uq_assets_job_external"),
    )
    op.create_index("ix_assets_job_id", "assets", ["job_id"], unique=False)
    op.create_index("ix_assets_external_key", "assets", ["external_key"], unique=False)

    op.create_table(
        "embed_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_external_key", sa.String(length=32), nullable=False),
        sa.Column("embed_id", sa.String(length=64), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("t_start_sec", sa.Float(), nullable=True),
        sa.Column("t_end_sec", sa.Float(), nullable=True),
        sa.Column(
            "whole_source_file",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "embed_id", name="uq_embed_targets_job_embed_id"),
    )
    op.create_index("ix_embed_targets_job_id", "embed_targets", ["job_id"], unique=False)
    op.create_index(
        "ix_embed_targets_asset_external",
        "embed_targets",
        ["asset_external_key"],
        unique=False,
    )
    op.create_index("ix_embed_targets_embed_id", "embed_targets", ["embed_id"], unique=False)

    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embed_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dims", sa.Integer(), nullable=False),
        sa.Column("vector", Vector(_EMB_DIM), nullable=False),
        sa.ForeignKeyConstraint(["embed_target_id"], ["embed_targets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("embed_target_id", name="uq_embeddings_embed_target_id"),
    )


def downgrade() -> None:
    op.drop_table("embeddings")
    op.drop_table("embed_targets")
    op.drop_table("assets")
    op.drop_table("jobs")
    op.execute("DROP EXTENSION IF EXISTS vector")
