"""Migration 0002 — Detection and Event models with PostGIS spatial geometry.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE eventtype AS ENUM (
            'POTHOLE', 'DAMAGED_ROAD', 'WATERLOGGING', 'MISSING_DIVIDER',
            'MISSING_ZEBRA_CROSSING', 'MISSING_SIGNBOARD', 'TRAFFIC_CONGESTION',
            'VEHICLE', 'PEDESTRIAN', 'OTHER'
        );
    EXCEPTION WHEN duplicate_object THEN null;
    END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE eventseverity AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
    EXCEPTION WHEN duplicate_object THEN null;
    END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE eventstatus AS ENUM (
            'DETECTED', 'VERIFIED', 'OPEN', 'ACKNOWLEDGED',
            'IN_PROGRESS', 'RESOLVED', 'REJECTED'
        );
    EXCEPTION WHEN duplicate_object THEN null;
    END $$;
    """)

    eventtype = postgresql.ENUM(
        "POTHOLE",
        "DAMAGED_ROAD",
        "WATERLOGGING",
        "MISSING_DIVIDER",
        "MISSING_ZEBRA_CROSSING",
        "MISSING_SIGNBOARD",
        "TRAFFIC_CONGESTION",
        "VEHICLE",
        "PEDESTRIAN",
        "OTHER",
        name="eventtype",
        create_type=False,
    )

    eventseverity = postgresql.ENUM(
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        name="eventseverity",
        create_type=False,
    )

    eventstatus = postgresql.ENUM(
        "DETECTED",
        "VERIFIED",
        "OPEN",
        "ACKNOWLEDGED",
        "IN_PROGRESS",
        "RESOLVED",
        "REJECTED",
        name="eventstatus",
        create_type=False,
    )

    # ── events table ──────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_type",
            eventtype,
            nullable=False,
        ),
        sa.Column(
            "severity",
            eventseverity,
            nullable=False,
            server_default="MEDIUM",
        ),
        sa.Column(
            "status",
            eventstatus,
            nullable=False,
            server_default="DETECTED",
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "location",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "first_detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bus_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_reference", sa.String(500), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bus_id"], ["buses.id"], ondelete="SET NULL", name="fk_events_bus_id"
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"], ["cameras.id"], ondelete="SET NULL", name="fk_events_camera_id"
        ),
    )
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_severity", "events", ["severity"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_first_detected_at", "events", ["first_detected_at"])
    op.create_index("ix_events_bus_id", "events", ["bus_id"])
    op.create_index("ix_events_camera_id", "events", ["camera_id"])

    # ── detections table ──────────────────────────────────────────────────────
    op.create_table(
        "detections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bus_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stream_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detection_type", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "location",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frame_reference", sa.String(500), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            ondelete="CASCADE",
            name="fk_detections_camera_id",
        ),
        sa.ForeignKeyConstraint(
            ["bus_id"],
            ["buses.id"],
            ondelete="CASCADE",
            name="fk_detections_bus_id",
        ),
        sa.ForeignKeyConstraint(
            ["stream_id"],
            ["streams.id"],
            ondelete="SET NULL",
            name="fk_detections_stream_id",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="SET NULL",
            name="fk_detections_event_id",
        ),
    )
    op.create_index("ix_detections_camera_id", "detections", ["camera_id"])
    op.create_index("ix_detections_bus_id", "detections", ["bus_id"])
    op.create_index("ix_detections_stream_id", "detections", ["stream_id"])
    op.create_index("ix_detections_detection_type", "detections", ["detection_type"])
    op.create_index("ix_detections_detected_at", "detections", ["detected_at"])
    op.create_index("ix_detections_event_id", "detections", ["event_id"])


def downgrade() -> None:
    op.drop_table("detections")
    op.drop_table("events")

    for enum_name in ["eventstatus", "eventseverity", "eventtype"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
