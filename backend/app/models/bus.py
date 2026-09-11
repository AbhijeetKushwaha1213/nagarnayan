"""
Bus SQLAlchemy model.

A Bus is the top-level physical entity in Nagar Nayan.
Each bus carries one or more cameras that generate streams.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class BusStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class Bus(Base, TimestampMixin):
    __tablename__ = "buses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    bus_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique vehicle registration / fleet number",
    )
    route_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Identifier of the route this bus operates on",
    )
    status: Mapped[BusStatus] = mapped_column(
        SAEnum(BusStatus, name="busstatus", create_type=True),
        nullable=False,
        default=BusStatus.active,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    cameras: Mapped[list[Camera]] = relationship(  # noqa: F821
        "Camera",
        back_populates="bus",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Bus id={self.id} number={self.bus_number!r} status={self.status}>"
