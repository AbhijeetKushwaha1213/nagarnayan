"""
Alert SQLAlchemy model.

An Alert represents an actionable notification generated from a municipal Event
that requires municipal operational intervention.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.event import EventSeverity

if TYPE_CHECKING:
    from app.models.event import Event


class AlertType(str, enum.Enum):
    """Categorization of actionable alerts."""

    MUNICIPAL_ISSUE = "MUNICIPAL_ISSUE"
    CRITICAL_INFRASTRUCTURE = "CRITICAL_INFRASTRUCTURE"
    TRAFFIC_HAZARD = "TRAFFIC_HAZARD"


class AlertStatus(str, enum.Enum):
    """Lifecycle state of an alert."""

    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class Alert(Base, TimestampMixin):
    """Actionable municipal notification synthesized from an Event."""

    __tablename__ = "alerts"
    __table_args__ = (
        # Partial unique index: at most one active alert (NEW or ACKNOWLEDGED) per event
        Index(
            "uq_alerts_active_event",
            "event_id",
            unique=True,
            postgresql_where=text("status IN ('NEW', 'ACKNOWLEDGED')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_type: Mapped[AlertType] = mapped_column(
        SAEnum(AlertType, name="alerttype", create_type=True),
        nullable=False,
        index=True,
    )
    severity: Mapped[EventSeverity] = mapped_column(
        SAEnum(EventSeverity, name="eventseverity", create_type=False),
        nullable=False,
        index=True,
    )
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, name="alertstatus", create_type=True),
        nullable=False,
        default=AlertStatus.NEW,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    event: Mapped[Event] = relationship(
        "Event",
        back_populates="alerts",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Alert id={self.id} event_id={self.event_id} type={self.alert_type} severity={self.severity} status={self.status}>"
