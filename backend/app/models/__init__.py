"""
Models package.

Imports all models so that Base.metadata contains every table.
Alembic imports this package to discover the full schema.
"""

from app.core.database import Base
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.bus import Bus, BusStatus
from app.models.camera import Camera, CameraStatus, CameraType
from app.models.detection import Detection
from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.models.stream import Stream, StreamProtocol, StreamStatus

__all__ = [
    "Base",
    "Alert",
    "AlertStatus",
    "AlertType",
    "Bus",
    "BusStatus",
    "Camera",
    "CameraType",
    "CameraStatus",
    "Stream",
    "StreamProtocol",
    "StreamStatus",
    "Detection",
    "Event",
    "EventType",
    "EventSeverity",
    "EventStatus",
]
