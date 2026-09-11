"""
WebSocket message envelope contracts and payload serializers.

Defines standard JSON contracts for real-time municipal updates:
  - Envelope: type, timestamp, data
  - Event payload: id, event_type, severity, status, coordinates, timestamps
  - Alert payload: id, event_id, alert_type, severity, status, title, message, timestamps
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.alert import Alert
from app.models.event import Event


class WebSocketMessageType(str, enum.Enum):
    """Standardized event types for WebSocket messages."""

    EVENT_CREATED = "event.created"
    EVENT_UPDATED = "event.updated"
    ALERT_CREATED = "alert.created"
    ALERT_UPDATED = "alert.updated"
    SYSTEM_PONG = "system.pong"


class WebSocketEnvelope(BaseModel):
    """Standard message envelope for all WebSocket broadcasts."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(..., description="Message topic or event name", examples=["event.created"])
    timestamp: str = Field(..., description="UTC ISO-8601 timestamp of message generation")
    data: dict[str, Any] = Field(..., description="Event or alert payload dictionary")


def serialize_event(event: Event) -> dict[str, Any]:
    """
    Format a municipal Event into a compact, JSON-serializable dictionary.

    Strictly preserves null coordinates without fabricating synthetic locations.
    """
    return {
        "id": str(event.id),
        "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
        "severity": event.severity.value if hasattr(event.severity, "value") else str(event.severity),
        "status": event.status.value if hasattr(event.status, "value") else str(event.status),
        "latitude": event.latitude if event.latitude is not None else None,
        "longitude": event.longitude if event.longitude is not None else None,
        "confidence": round(event.confidence, 4),
        "first_detected_at": (
            event.first_detected_at.isoformat()
            if isinstance(event.first_detected_at, datetime)
            else str(event.first_detected_at)
        ),
        "last_detected_at": (
            event.last_detected_at.isoformat()
            if isinstance(event.last_detected_at, datetime)
            else str(event.last_detected_at)
        ),
        "bus_id": str(event.bus_id) if event.bus_id else None,
        "camera_id": str(event.camera_id) if event.camera_id else None,
        "metadata": dict(event.extra_metadata or {}),
    }


def serialize_alert(alert: Alert) -> dict[str, Any]:
    """
    Format a municipal Alert into a compact, JSON-serializable dictionary.

    Excludes redundant entire Event trees while referencing event_id.
    """
    return {
        "id": str(alert.id),
        "event_id": str(alert.event_id),
        "alert_type": alert.alert_type.value if hasattr(alert.alert_type, "value") else str(alert.alert_type),
        "severity": alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
        "status": alert.status.value if hasattr(alert.status, "value") else str(alert.status),
        "title": alert.title,
        "message": alert.message,
        "created_at": (
            alert.created_at.isoformat()
            if isinstance(alert.created_at, datetime)
            else str(alert.created_at)
        ),
        "acknowledged_at": (
            alert.acknowledged_at.isoformat()
            if isinstance(alert.acknowledged_at, datetime)
            else None
        ),
        "resolved_at": (
            alert.resolved_at.isoformat()
            if isinstance(alert.resolved_at, datetime)
            else None
        ),
        "metadata": dict(alert.extra_metadata or {}),
    }


def build_envelope(message_type: str | WebSocketMessageType, data: dict[str, Any]) -> dict[str, Any]:
    """Construct a standardized message envelope dictionary."""
    msg_type_str = message_type.value if isinstance(message_type, WebSocketMessageType) else message_type
    return {
        "type": msg_type_str,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
