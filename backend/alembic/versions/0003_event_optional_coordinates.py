"""Migration 0003 — Make coordinates optional in events and detections tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make latitude and longitude nullable on events
    op.alter_column("events", "latitude", existing_type=sa.Float(), nullable=True)
    op.alter_column("events", "longitude", existing_type=sa.Float(), nullable=True)

    # Make latitude and longitude nullable on detections
    op.alter_column("detections", "latitude", existing_type=sa.Float(), nullable=True)
    op.alter_column("detections", "longitude", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.alter_column("detections", "longitude", existing_type=sa.Float(), nullable=False)
    op.alter_column("detections", "latitude", existing_type=sa.Float(), nullable=False)
    op.alter_column("events", "longitude", existing_type=sa.Float(), nullable=False)
    op.alter_column("events", "latitude", existing_type=sa.Float(), nullable=False)
