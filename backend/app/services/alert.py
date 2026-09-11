"""Alert service — business logic, policy evaluation, and lifecycle enforcement for municipal Alerts."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertStatus, AlertType
from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.repositories.alert import AlertRepository
from app.schemas.alert import AlertUpdate
from app.websocket.publisher import WebSocketPublisher, publisher as default_publisher

logger = logging.getLogger(__name__)

# Valid state machine transitions for Alert lifecycle
ALLOWED_LIFECYCLE_TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.NEW: {
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.DISMISSED,
        AlertStatus.RESOLVED,
    },
    AlertStatus.ACKNOWLEDGED: {
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
    },
    AlertStatus.RESOLVED: set(),
    AlertStatus.DISMISSED: set(),
}

# Actionable event severities that can trigger alerts
ACTIONABLE_SEVERITIES: set[EventSeverity] = {
    EventSeverity.CRITICAL,
    EventSeverity.HIGH,
}

# Actionable event statuses that can trigger alerts
ACTIONABLE_EVENT_STATUSES: set[EventStatus] = {
    EventStatus.DETECTED,
    EventStatus.VERIFIED,
    EventStatus.OPEN,
}


class AlertService:
    """Service orchestrating municipal Alert generation and lifecycle management."""

    def __init__(
        self,
        session: AsyncSession,
        repository: AlertRepository | None = None,
        publisher: WebSocketPublisher | None = None,
    ) -> None:
        self._session = session
        self.repo = repository if repository is not None else AlertRepository(session)
        self._publisher = publisher if publisher is not None else default_publisher

    @staticmethod
    def should_generate_alert(event: Event) -> bool:
        """
        Evaluate municipal alert policy against an Event.

        Rules:
          - Event severity must be CRITICAL or HIGH.
          - Event status must be actionable (DETECTED, VERIFIED, OPEN).
          - RESOLVED or REJECTED events never generate alerts.
          - MEDIUM and LOW events do not automatically generate alerts.
        """
        if event.status not in ACTIONABLE_EVENT_STATUSES:
            return False
        if event.severity not in ACTIONABLE_SEVERITIES:
            return False
        return True

    @staticmethod
    def map_event_to_alert_type(event: Event) -> AlertType:
        """Deterministically map an Event to an AlertType."""
        if (
            event.severity == EventSeverity.CRITICAL
            or event.event_type == EventType.MISSING_DIVIDER
        ):
            return AlertType.CRITICAL_INFRASTRUCTURE
        if event.event_type == EventType.TRAFFIC_CONGESTION:
            return AlertType.TRAFFIC_HAZARD
        return AlertType.MUNICIPAL_ISSUE

    @staticmethod
    def generate_alert_content(event: Event) -> tuple[str, str]:
        """
        Generate deterministic, human-readable title and message.

        Strictly avoids fabricating geographic addresses or locations.
        """
        if event.event_type == EventType.POTHOLE and event.severity == EventSeverity.HIGH:
            title = "High Priority Pothole Detected"
        elif event.event_type == EventType.MISSING_DIVIDER:
            title = "Critical Road Divider Issue"
        else:
            sev_label = event.severity.value.capitalize()
            type_label = event.event_type.value.replace("_", " ").title()
            title = f"{sev_label} Priority {type_label} Issue"

        issue_desc = event.event_type.value.replace("_", " ").lower()
        message = (
            f"Persistent {issue_desc} detected by bus-camera observations. "
            f"Confidence: {event.confidence:.2f}"
        )
        return title, message

    async def process_event_for_alert(self, event: Event) -> Alert | None:
        """
        Evaluate an Event and create an Alert if policy requires it and no active alert exists.

        Anti-Flooding / Idempotency:
          - If an active alert (NEW or ACKNOWLEDGED) already exists for this Event,
            a new alert is suppressed and the existing active alert is returned.
          - If previous alerts for this Event were RESOLVED or DISMISSED, and the Event
            remains or becomes actionable again, a new alert is generated.
        """
        if not self.should_generate_alert(event):
            logger.debug(
                "Event %s (type=%s, severity=%s, status=%s) does not qualify for an Alert.",
                event.id,
                event.event_type.value,
                event.severity.value,
                event.status.value,
            )
            return None

        # Check for existing active alert for this event with row-level lock
        active_alert = await self.repo.find_active_alert_by_event(
            event.id, for_update=True
        )
        if active_alert is not None:
            active_alert._is_new = False
            logger.info(
                "Active alert %s (%s) already exists for Event %s; suppressing duplicate alert.",
                active_alert.id,
                active_alert.status.value,
                event.id,
            )
            return active_alert

        # Synthesize new alert
        alert_type = self.map_event_to_alert_type(event)
        title, message = self.generate_alert_content(event)

        metadata: dict[str, Any] = {
            "event_type": event.event_type.value,
            "event_severity": event.severity.value,
            "confidence": round(event.confidence, 4),
            "first_detected_at": (
                event.first_detected_at.isoformat() if event.first_detected_at else None
            ),
            "last_detected_at": (
                event.last_detected_at.isoformat() if event.last_detected_at else None
            ),
        }
        if event.latitude is not None and event.longitude is not None:
            metadata["latitude"] = event.latitude
            metadata["longitude"] = event.longitude

        now = datetime.now(timezone.utc)
        new_alert = Alert(
            id=uuid.uuid4(),
            event_id=event.id,
            alert_type=alert_type,
            severity=event.severity,
            status=AlertStatus.NEW,
            title=title,
            message=message,
            extra_metadata=metadata,
            created_at=now,
            updated_at=now,
        )

        new_alert = await self.repo.create(new_alert)
        await self._session.flush()
        new_alert._is_new = True

        logger.info(
            "Synthesized Alert %s (%s, severity=%s, status=NEW) for Event %s",
            new_alert.id,
            alert_type.value,
            new_alert.severity.value,
            event.id,
        )
        return new_alert

    async def get_alert(self, alert_id: uuid.UUID) -> Alert:
        """Retrieve an Alert by ID, including its parent Event summary."""
        alert = await self.repo.get_by_id_with_event(alert_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert {alert_id} not found",
            )
        return alert

    async def list_alerts(
        self,
        status_filter: AlertStatus | None = None,
        severity: EventSeverity | None = None,
        event_id: uuid.UUID | None = None,
        alert_type: AlertType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        """List alerts with filtering and pagination."""
        return await self.repo.list(
            status=status_filter,
            severity=severity,
            event_id=event_id,
            alert_type=alert_type,
            limit=limit,
            offset=offset,
        )

    async def update_alert(self, alert_id: uuid.UUID, data: AlertUpdate) -> Alert:
        """
        Update an Alert (lifecycle transition and/or metadata update).

        Validates lifecycle state transitions:
          NEW -> ACKNOWLEDGED
          ACKNOWLEDGED -> RESOLVED
          NEW -> DISMISSED
          ACKNOWLEDGED -> DISMISSED
          NEW -> RESOLVED

        Rejects invalid transitions (e.g. RESOLVED -> NEW).
        """
        alert = await self.repo.get_by_id_with_event(alert_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert {alert_id} not found",
            )

        # Handle status lifecycle transition
        if data.status is not None and data.status != alert.status:
            allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(alert.status, set())
            if data.status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Invalid lifecycle transition from {alert.status.value} to "
                        f"{data.status.value}"
                    ),
                )

            now = datetime.now(timezone.utc)
            if data.status == AlertStatus.ACKNOWLEDGED:
                if alert.acknowledged_at is None:
                    alert.acknowledged_at = now
            elif data.status == AlertStatus.RESOLVED:
                if alert.resolved_at is None:
                    alert.resolved_at = now

            alert.status = data.status

        # Handle metadata update
        if data.metadata is not None:
            current_metadata = dict(alert.extra_metadata or {})
            current_metadata.update(data.metadata)
            alert.extra_metadata = current_metadata

        alert = await self.repo.update(alert)
        await self._session.commit()
        await self._session.refresh(alert)
        await self._publisher.publish_alert_updated(alert)
        return alert
