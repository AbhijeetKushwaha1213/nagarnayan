"""
Camera SQLAlchemy model.

A Camera belongs to a Bus and generates one or more Streams.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class CameraType(str, enum.Enum):
    front = "front"
    rear = "rear"
    side = "side"
    interior = "interior"


class CameraStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    bus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_type: Mapped[CameraType] = mapped_column(
        SAEnum(CameraType, name="cameratype", create_type=True),
        nullable=False,
    )
    status: Mapped[CameraStatus] = mapped_column(
        SAEnum(CameraStatus, name="camerastatus", create_type=True),
        nullable=False,
        default=CameraStatus.active,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    bus: Mapped[Bus] = relationship(  # noqa: F821
        "Bus",
        back_populates="cameras",
    )
    streams: Mapped[list[Stream]] = relationship(  # noqa: F821
        "Stream",
        back_populates="camera",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Camera id={self.id} type={self.camera_type} bus={self.bus_id}>"
