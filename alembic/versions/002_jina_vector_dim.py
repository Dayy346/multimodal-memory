"""Resize pgvector column for Jina v5 omni-small (1024-d).

Revision ID: 002_jina_dim
Revises: 001_initial
Create Date: 2026-08-31

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "002_jina_dim"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_DIM = 1024
_OLD_DIM = 3072


def upgrade() -> None:
    # Previous Gemini vectors cannot be reused in the Jina 1024-d space.
    op.execute("DELETE FROM embeddings")
    op.execute("ALTER TABLE embeddings DROP COLUMN vector")
    op.execute(f"ALTER TABLE embeddings ADD COLUMN vector vector({_NEW_DIM}) NOT NULL")


def downgrade() -> None:
    op.execute("DELETE FROM embeddings")
    op.execute("ALTER TABLE embeddings DROP COLUMN vector")
    op.execute(f"ALTER TABLE embeddings ADD COLUMN vector vector({_OLD_DIM}) NOT NULL")
