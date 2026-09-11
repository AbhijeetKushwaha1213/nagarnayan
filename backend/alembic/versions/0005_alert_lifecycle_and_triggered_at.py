"""Migration 0005 — Phase 6: Alert lifecycle (ACTIVE status), triggered_at column, and updated active-event partial unique index.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add 'ACTIVE' value to alertstatus enum
    # PostgreSQL requires ALTER TYPE ... ADD VALUE outside of a transaction or executed conditionally
    op.execute("ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'ACTIVE' BEFORE 'NEW'")

    # 2. Add triggered_at column with default = now()
    op.add_column(
        "alerts",
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"])

    # 3. Update partial unique index to include ACTIVE alongside NEW and ACKNOWLEDGED
    op.drop_index("uq_alerts_active_event", table_name="alerts")
    op.create_index(
        "uq_alerts_active_event",
        "alerts",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'NEW', 'ACKNOWLEDGED')"),
    )


def downgrade() -> None:
    # 1. Revert partial unique index to only NEW, ACKNOWLEDGED
    op.drop_index("uq_alerts_active_event", table_name="alerts")
    op.create_index(
        "uq_alerts_active_event",
        "alerts",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('NEW', 'ACKNOWLEDGED')"),
    )

    # 2. Drop triggered_at index and column
    op.drop_index("ix_alerts_triggered_at", table_name="alerts")
    op.drop_column("alerts", "triggered_at")

    # Note: PostgreSQL does not support removing values from an enum type directly without recreating it.
