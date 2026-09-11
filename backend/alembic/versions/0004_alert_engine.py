"""Migration 0004 — Alert Engine: alerts table, enums, and active-event partial unique index.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────────
    alerttype = postgresql.ENUM(
        "MUNICIPAL_ISSUE",
        "CRITICAL_INFRASTRUCTURE",
        "TRAFFIC_HAZARD",
        name="alerttype",
        create_type=False,
    )
    alerttype.create(op.get_bind(), checkfirst=True)

    alertstatus = postgresql.ENUM(
        "NEW",
        "ACKNOWLEDGED",
        "RESOLVED",
        "DISMISSED",
        name="alertstatus",
        create_type=False,
    )
    alertstatus.create(op.get_bind(), checkfirst=True)

    # ── alerts table ──────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "alert_type",
            sa.Enum(
                "MUNICIPAL_ISSUE",
                "CRITICAL_INFRASTRUCTURE",
                "TRAFFIC_HAZARD",
                name="alerttype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
                name="eventseverity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "ACKNOWLEDGED",
                "RESOLVED",
                "DISMISSED",
                name="alertstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.create_index("ix_alerts_event_id", "alerts", ["event_id"])
    op.create_index("ix_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])

    # Partial unique index: at most one active alert (NEW, ACKNOWLEDGED) per event
    op.create_index(
        "uq_alerts_active_event",
        "alerts",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('NEW', 'ACKNOWLEDGED')"),
    )


def downgrade() -> None:
    op.drop_index("uq_alerts_active_event", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_alert_type", table_name="alerts")
    op.drop_index("ix_alerts_event_id", table_name="alerts")
    op.drop_table("alerts")

    sa.Enum(name="alertstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="alerttype").drop(op.get_bind(), checkfirst=True)
