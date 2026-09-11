"""
WebSocket publisher for Nagar Nayan municipal Events and Alerts.

Centralizes message formatting, envelope construction, and broadcast dispatching.
Provides strict error isolation so that WebSocket broadcast errors never impact
database transactions or business logic execution.
"""

from __future__ import annotations

import logging

from app.models.alert import Alert
from app.models.event import Event
from app.websocket.manager import ConnectionManager, connection_manager
from app.websocket.schemas import (
    WebSocketMessageType,
    build_envelope,
    serialize_alert,
    serialize_event,
)

logger = logging.getLogger(__name__)


class WebSocketPublisher:
    """Centralized dispatcher for real-time municipal updates."""

    def __init__(self, manager: ConnectionManager | None = None) -> None:
        self._manager = manager if manager is not None else connection_manager

    async def publish_event_created(self, event: Event) -> None:
        """Broadcast event.created notification."""
        try:
            payload = serialize_event(event)
            envelope = build_envelope(WebSocketMessageType.EVENT_CREATED, payload)
            await self._manager.broadcast(envelope)
            logger.debug("Published WebSocket event.created for Event %s", event.id)
        except Exception as exc:
            logger.error("Failed to publish event.created for Event %s: %s", event.id, exc)

    async def publish_event_updated(self, event: Event) -> None:
        """Broadcast event.updated notification."""
        try:
            payload = serialize_event(event)
            envelope = build_envelope(WebSocketMessageType.EVENT_UPDATED, payload)
            await self._manager.broadcast(envelope)
            logger.debug("Published WebSocket event.updated for Event %s", event.id)
        except Exception as exc:
            logger.error("Failed to publish event.updated for Event %s: %s", event.id, exc)

    async def publish_alert_created(self, alert: Alert) -> None:
        """Broadcast alert.created notification."""
        try:
            payload = serialize_alert(alert)
            envelope = build_envelope(WebSocketMessageType.ALERT_CREATED, payload)
            await self._manager.broadcast(envelope)
            logger.debug("Published WebSocket alert.created for Alert %s", alert.id)
        except Exception as exc:
            logger.error("Failed to publish alert.created for Alert %s: %s", alert.id, exc)

    async def publish_alert_updated(self, alert: Alert) -> None:
        """Broadcast alert.updated notification."""
        try:
            payload = serialize_alert(alert)
            envelope = build_envelope(WebSocketMessageType.ALERT_UPDATED, payload)
            await self._manager.broadcast(envelope)
            logger.debug("Published WebSocket alert.updated for Alert %s", alert.id)
        except Exception as exc:
            logger.error("Failed to publish alert.updated for Alert %s: %s", alert.id, exc)


# Global singleton instance
publisher = WebSocketPublisher()
