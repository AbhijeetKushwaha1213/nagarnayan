"""
Event SQLAlchemy model.

An Event represents a validated, meaningful urban issue (e.g. Pothole, Damaged Road).
Multiple raw Detections may optionally link to a single Event.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.base import TimestampMixin


class EventType(str, enum.Enum):
    POTHOLE = "POTHOLE"
    DAMAGED_ROAD = "DAMAGED_ROAD"
    WATERLOGGING = "WATERLOGGING"
    MISSING_DIVIDER = "MISSING_DIVIDER"
    MISSING_ZEBRA_CROSSING = "MISSING_ZEBRA_CROSSING"
    MISSING_SIGNBOARD = "MISSING_SIGNBOARD"
    TRAFFIC_CONGESTION = "TRAFFIC_CONGESTION"
    VEHICLE = "VEHICLE"
    PEDESTRIAN = "PEDESTRIAN"
    OTHER = "OTHER"


class EventSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    VERIFIED = "VERIFIED"
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


# Statuses eligible for automatic spatial-temporal correlation and detection linkage
ACTIVE_EVENT_STATUSES: set[EventStatus] = {
    EventStatus.DETECTED,
    EventStatus.VERIFIED,
    EventStatus.OPEN,
    EventStatus.ACKNOWLEDGED,
    EventStatus.IN_PROGRESS,
}

# Terminal statuses where the municipal issue is closed/dismissed and must not absorb new detections
TERMINAL_EVENT_STATUSES: set[EventStatus] = {
    EventStatus.RESOLVED,
    EventStatus.REJECTED,
}


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType, name="eventtype", create_type=True),
        nullable=False,
        index=True,
    )
    severity: Mapped[EventSeverity] = mapped_column(
        SAEnum(EventSeverity, name="eventseverity", create_type=True),
        nullable=False,
        default=EventSeverity.MEDIUM,
        index=True,
    )
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, name="eventstatus", create_type=True),
        nullable=False,
        default=EventStatus.DETECTED,
        index=True,
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
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    bus_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    detections: Mapped[list[Detection]] = relationship(  # noqa: F821
        "Detection",
        back_populates="event",
        lazy="selectin",
    )
    alerts: Mapped[list[Alert]] = relationship(  # noqa: F821
        "Alert",
        back_populates="event",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} type={self.event_type} status={self.status} severity={self.severity}>"
