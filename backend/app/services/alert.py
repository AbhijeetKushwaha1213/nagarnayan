"""Alert service — business logic, policy evaluation, and lifecycle enforcement for municipal Alerts."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.event import (
    ACTIVE_EVENT_STATUSES,
    Event,
    EventSeverity,
    EventStatus,
    EventType,
)
from app.repositories.alert import AlertRepository
from app.schemas.alert import AlertManualCreate, AlertUpdate
from app.websocket.publisher import WebSocketPublisher, publisher as default_publisher

logger = logging.getLogger(__name__)

# Valid state machine transitions for Alert lifecycle
ALLOWED_LIFECYCLE_TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.ACTIVE: {
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.DISMISSED,
    },
    AlertStatus.NEW: {
        AlertStatus.ACTIVE,
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.DISMISSED,
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

# Numerical severity ranking for escalation comparison
SEVERITY_ORDER: dict[EventSeverity, int] = {
    EventSeverity.LOW: 1,
    EventSeverity.MEDIUM: 2,
    EventSeverity.HIGH: 3,
    EventSeverity.CRITICAL: 4,
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
          - Event status must be actionable (DETECTED, VERIFIED, OPEN, ACKNOWLEDGED, IN_PROGRESS).
          - RESOLVED or REJECTED events never generate alerts.
          - CRITICAL: immediate alert generation.
          - HIGH: creates an alert.
          - MEDIUM: creates an alert ONLY when meeting explicit configured supporting thresholds:
              * supporting detection_count >= ALERT_MEDIUM_THRESHOLD_DETECTION_COUNT (default 3), OR
              * distinct reporting buses >= ALERT_MEDIUM_THRESHOLD_DISTINCT_BUSES (default 2), OR
              * persistence duration >= ALERT_MEDIUM_THRESHOLD_PERSISTENCE_SECONDS (default 120s).
          - LOW: normally suppressed (does not create alert).
        """
        if event.status not in ACTIVE_EVENT_STATUSES:
            return False
        if event.status in (EventStatus.RESOLVED, EventStatus.REJECTED):
            return False

        # CRITICAL and HIGH qualify immediately
        if event.severity in (EventSeverity.CRITICAL, EventSeverity.HIGH):
            return True

        # MEDIUM qualifies only when supporting evidence thresholds are met
        if event.severity == EventSeverity.MEDIUM:
            metadata = dict(event.extra_metadata or {})
            detection_count = int(metadata.get("detection_count", 1))
            reporting_buses = list(metadata.get("reporting_buses", []))
            if "distinct_buses" in metadata:
                distinct_bus_count = int(metadata["distinct_buses"])
            elif reporting_buses:
                distinct_bus_count = len(set(reporting_buses))
            elif getattr(event, "bus_id", None):
                distinct_bus_count = 1
            else:
                distinct_bus_count = 0
            duration_seconds = 0.0
            if event.first_detected_at and event.last_detected_at:
                duration_seconds = max(
                    0.0,
                    (event.last_detected_at - event.first_detected_at).total_seconds(),
                )

            threshold_count = getattr(settings, "ALERT_MEDIUM_THRESHOLD_DETECTION_COUNT", 3)
            threshold_buses = getattr(settings, "ALERT_MEDIUM_THRESHOLD_DISTINCT_BUSES", 2)
            threshold_duration = getattr(settings, "ALERT_MEDIUM_THRESHOLD_PERSISTENCE_SECONDS", 120)

            if (
                detection_count >= threshold_count
                or distinct_bus_count >= threshold_buses
                or duration_seconds >= threshold_duration
            ):
                return True
            return False

        # LOW does not generate alerts
        return False

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
        Evaluate an Event and create or escalate an Alert if policy requires it.

        Anti-Flooding / Idempotency / Escalation:
          - If an active alert (ACTIVE, NEW, or ACKNOWLEDGED) already exists for this Event:
            * Check for severity escalation: if Event severity is higher than active Alert severity,
              escalate the alert's severity, title, message, and metadata.
            * Otherwise suppress duplicate creation and return the existing active alert.
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
            active_alert._is_escalated = False

            # Severity escalation: if event severity outranks active alert severity, escalate alert
            current_alert_rank = SEVERITY_ORDER.get(active_alert.severity, 1)
            event_rank = SEVERITY_ORDER.get(event.severity, 1)

            if event_rank > current_alert_rank:
                logger.info(
                    "Escalating active Alert %s (%s) from %s -> %s for Event %s",
                    active_alert.id,
                    active_alert.status.value,
                    active_alert.severity.value,
                    event.severity.value,
                    event.id,
                )
                active_alert.severity = event.severity
                title, message = self.generate_alert_content(event)
                active_alert.title = title
                active_alert.message = message
                active_alert.alert_type = self.map_event_to_alert_type(event)
                meta = dict(active_alert.extra_metadata or {})
                meta["event_severity"] = event.severity.value
                meta["escalated_at"] = datetime.now(timezone.utc).isoformat()
                active_alert.extra_metadata = meta
                active_alert._is_escalated = True
                await self.repo.update(active_alert)
                await self._session.flush()

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
            status=AlertStatus.ACTIVE,
            title=title,
            message=message,
            triggered_at=now,
            extra_metadata=metadata,
            created_at=now,
            updated_at=now,
        )

        new_alert = await self.repo.create(new_alert)
        await self._session.flush()
        new_alert._is_new = True

        logger.info(
            "Synthesized Alert %s (%s, severity=%s, status=ACTIVE) for Event %s",
            new_alert.id,
            alert_type.value,
            new_alert.severity.value,
            event.id,
        )
        return new_alert

    async def create_manual_alert(self, data: AlertManualCreate) -> Alert:
        """
        Create a manual municipal alert via POST /api/v1/alerts.

        Validates event existence and enforces active-alert deduplication.
        """
        from app.repositories.event import EventRepository

        event_repo = EventRepository(self._session)
        event = await event_repo.get_by_id(data.event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {data.event_id} not found",
            )

        # Idempotency / deduplication check
        existing_active = await self.repo.find_active_alert_by_event(
            data.event_id, for_update=True
        )
        if existing_active is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Active alert {existing_active.id} ({existing_active.status.value}) "
                    f"already exists for Event {data.event_id}"
                ),
            )

        alert_type = data.alert_type or self.map_event_to_alert_type(event)
        severity = data.severity or event.severity
        now = datetime.now(timezone.utc)

        metadata = dict(data.metadata)
        metadata["created_by"] = "operator_manual"
        metadata["event_type"] = event.event_type.value

        new_alert = Alert(
            id=uuid.uuid4(),
            event_id=event.id,
            alert_type=alert_type,
            severity=severity,
            status=AlertStatus.ACTIVE,
            title=data.title,
            message=data.message,
            triggered_at=now,
            created_at=now,
            updated_at=now,
            extra_metadata=metadata,
        )
        new_alert = await self.repo.create(new_alert)
        await self._session.commit()
        await self._session.refresh(new_alert)
        await self._publisher.publish_alert_created(new_alert)
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
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        """List alerts with filtering and pagination."""
        return await self.repo.list(
            status=status_filter,
            severity=severity,
            event_id=event_id,
            alert_type=alert_type,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            limit=limit,
            offset=offset,
        )

    async def update_alert(self, alert_id: uuid.UUID, data: AlertUpdate) -> Alert:
        """
        Update an Alert (lifecycle transition and/or metadata update).

        Validates lifecycle state transitions:
          ACTIVE / NEW -> ACKNOWLEDGED
          ACKNOWLEDGED -> RESOLVED
          ACTIVE / NEW -> DISMISSED
          ACKNOWLEDGED -> DISMISSED
          ACTIVE / NEW -> RESOLVED

        Rejects invalid transitions (e.g. RESOLVED -> ACTIVE).
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
