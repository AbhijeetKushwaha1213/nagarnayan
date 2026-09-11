"""
Stream SQLAlchemy model.

A Stream belongs to a Camera and records RTSP stream metadata.

IMPORTANT: This model stores stream metadata only.
The backend does NOT ingest, process, or connect to the RTSP stream.
The actual RTSP streaming is handled by the separate FFmpeg/MediaMTX server.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class StreamProtocol(str, enum.Enum):
    rtsp = "rtsp"


class StreamStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class Stream(Base, TimestampMixin):
    __tablename__ = "streams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stream_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="RTSP endpoint URL — stored as metadata, not consumed by this service",
    )
    protocol: Mapped[StreamProtocol] = mapped_column(
        SAEnum(StreamProtocol, name="streamprotocol", create_type=True),
        nullable=False,
        default=StreamProtocol.rtsp,
    )
    status: Mapped[StreamStatus] = mapped_column(
        SAEnum(StreamStatus, name="streamstatus", create_type=True),
        nullable=False,
        default=StreamStatus.inactive,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the stream was last started (set by the AI service)",
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the stream was last stopped",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    camera: Mapped[Camera] = relationship(  # noqa: F821
        "Camera",
        back_populates="streams",
    )

    def __repr__(self) -> str:
        return f"<Stream id={self.id} url={self.stream_url!r} status={self.status}>"
