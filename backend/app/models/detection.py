"""
Detection SQLAlchemy model.

A Detection is a raw AI observation emitted by an external AI Video Intelligence Service.
A Detection records what was seen, when, where, and with what confidence.
It can optionally reference a validated urban Event (via event_id).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Detection(Base):
    __tablename__ = "detections"

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
    bus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stream_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("streams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional foreign key to the originating Stream",
    )
    detection_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of detected object/issue, e.g. POTHOLE, DAMAGED_ROAD",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="AI inference confidence score between 0.0 and 1.0",
    )
    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Timestamp when the detection was observed by the camera/model",
    )
    frame_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Frame number, timestamp offset, or storage image URI",
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
        comment="Arbitrary AI-specific metadata (e.g. bounding boxes, model version)",
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional foreign key to a validated urban Event",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    bus: Mapped[Bus] = relationship(  # noqa: F821
        "Bus",
        lazy="selectin",
    )
    camera: Mapped[Camera] = relationship(  # noqa: F821
        "Camera",
        lazy="selectin",
    )
    stream: Mapped[Stream | None] = relationship(  # noqa: F821
        "Stream",
        lazy="selectin",
    )
    event: Mapped[Event | None] = relationship(  # noqa: F821
        "Event",
        back_populates="detections",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Detection id={self.id} type={self.detection_type!r} conf={self.confidence} bus={self.bus_id}>"
