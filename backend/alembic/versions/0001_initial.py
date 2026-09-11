"""Initial migration — PostGIS extension, buses, cameras, streams tables.

Revision ID: 0001
Revises:
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── PostGIS extension ─────────────────────────────────────────────────────
    # Enables geographic types and functions for future spatial columns.
    # No spatial columns are added in this migration — only the extension.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ── Enum types ────────────────────────────────────────────────────────────
    busstatus = postgresql.ENUM("active", "inactive", name="busstatus", create_type=False)
    busstatus.create(op.get_bind(), checkfirst=True)

    cameratype = postgresql.ENUM(
        "front", "rear", "side", "interior", name="cameratype", create_type=False
    )
    cameratype.create(op.get_bind(), checkfirst=True)

    camerastatus = postgresql.ENUM(
        "active", "inactive", "error", name="camerastatus", create_type=False
    )
    camerastatus.create(op.get_bind(), checkfirst=True)

    streamprotocol = postgresql.ENUM("rtsp", name="streamprotocol", create_type=False)
    streamprotocol.create(op.get_bind(), checkfirst=True)

    streamstatus = postgresql.ENUM(
        "active", "inactive", "error", name="streamstatus", create_type=False
    )
    streamstatus.create(op.get_bind(), checkfirst=True)

    # ── buses ─────────────────────────────────────────────────────────────────
    op.create_table(
        "buses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bus_number", sa.String(50), nullable=False),
        sa.Column("route_id", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="busstatus", create_type=False),
            nullable=False,
            server_default="active",
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
    )
    op.create_unique_constraint("uq_buses_bus_number", "buses", ["bus_number"])
    op.create_index("ix_buses_bus_number", "buses", ["bus_number"])

    # ── cameras ───────────────────────────────────────────────────────────────
    op.create_table(
        "cameras",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bus_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "camera_type",
            sa.Enum(
                "front", "rear", "side", "interior",
                name="cameratype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "inactive", "error",
                name="camerastatus",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
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
            ["bus_id"], ["buses.id"], ondelete="CASCADE", name="fk_cameras_bus_id"
        ),
    )
    op.create_index("ix_cameras_bus_id", "cameras", ["bus_id"])

    # ── streams ───────────────────────────────────────────────────────────────
    op.create_table(
        "streams",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stream_url", sa.String(500), nullable=False),
        sa.Column(
            "protocol",
            sa.Enum("rtsp", name="streamprotocol", create_type=False),
            nullable=False,
            server_default="rtsp",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "inactive", "error",
                name="streamstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="inactive",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
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
            ["camera_id"],
            ["cameras.id"],
            ondelete="CASCADE",
            name="fk_streams_camera_id",
        ),
    )
    op.create_index("ix_streams_camera_id", "streams", ["camera_id"])


def downgrade() -> None:
    op.drop_table("streams")
    op.drop_table("cameras")
    op.drop_table("buses")

    # Drop enum types
    for enum_name in [
        "streamstatus", "streamprotocol", "camerastatus", "cameratype", "busstatus"
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    # Note: PostGIS extension is not dropped to avoid data loss
    # op.execute("DROP EXTENSION IF EXISTS postgis")
