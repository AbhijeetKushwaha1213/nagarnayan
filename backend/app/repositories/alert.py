"""Alert repository — database queries for Alert entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alert import Alert, AlertStatus, AlertType
from app.models.event import EventSeverity
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    """Database repository for municipal Alert operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Alert, session)

    async def list(
        self,
        status: AlertStatus | None = None,
        severity: EventSeverity | None = None,
        event_id: uuid.UUID | None = None,
        alert_type: AlertType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        """Query alerts with optional filtering and pagination."""
        query = select(Alert).options(selectinload(Alert.event))
        if status is not None:
            query = query.where(Alert.status == status)
        if severity is not None:
            query = query.where(Alert.severity == severity)
        if event_id is not None:
            query = query.where(Alert.event_id == event_id)
        if alert_type is not None:
            query = query.where(Alert.alert_type == alert_type)

        query = query.order_by(Alert.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_active_alert_by_event(
        self,
        event_id: uuid.UUID,
        for_update: bool = False,
    ) -> Alert | None:
        """
        Find an existing active alert (NEW or ACKNOWLEDGED) for the specified Event.

        Optionally applies row-level locking (FOR UPDATE) to prevent race conditions.
        """
        query = (
            select(Alert)
            .where(
                Alert.event_id == event_id,
                Alert.status.in_([AlertStatus.NEW, AlertStatus.ACKNOWLEDGED]),
            )
            .options(selectinload(Alert.event))
        )
        if for_update:
            query = query.with_for_update()

        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_id_with_event(self, alert_id: uuid.UUID) -> Alert | None:
        """Fetch alert by ID with event relationship preloaded."""
        query = (
            select(Alert)
            .where(Alert.id == alert_id)
            .options(selectinload(Alert.event))
        )
        result = await self.session.execute(query)
        return result.scalars().first()
