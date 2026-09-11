"""
Event service — business logic for validated urban issues.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.repositories.bus import BusRepository
from app.repositories.camera import CameraRepository
from app.repositories.event import EventRepository
from app.schemas.event import EventCreate, EventUpdate
from app.websocket.publisher import WebSocketPublisher, publisher as default_publisher


class EventService:
    def __init__(
        self,
        session: AsyncSession,
        publisher: WebSocketPublisher | None = None,
    ) -> None:
        self.repo = EventRepository(session)
        self._bus_repo = BusRepository(session)
        self._camera_repo = CameraRepository(session)
        self._publisher = publisher if publisher is not None else default_publisher
        self._session = session

    async def list_events(
        self,
        event_type: EventType | None = None,
        status: EventStatus | None = None,
        severity: EventSeverity | None = None,
        bus_id: uuid.UUID | None = None,
        camera_id: uuid.UUID | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        return await self.repo.list(
            event_type=event_type,
            status=status,
            severity=severity,
            bus_id=bus_id,
            camera_id=camera_id,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            limit=limit,
            offset=offset,
        )

    async def get_event(self, event_id: uuid.UUID) -> Event:
        event = await self.repo.get_by_id(event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found",
            )
        return event

    async def create_event(self, data: EventCreate) -> Event:
        # Validate optional referenced entities
        if data.bus_id is not None:
            bus = await self._bus_repo.get_by_id(data.bus_id)
            if bus is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Bus {data.bus_id} does not exist",
                )

        if data.camera_id is not None:
            camera = await self._camera_repo.get_by_id(data.camera_id)
            if camera is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Camera {data.camera_id} does not exist",
                )

        now = datetime.now(timezone.utc)
        payload = data.model_dump()
        extra_metadata = payload.pop("metadata", {})

        first_detected_at = payload.pop("first_detected_at", None) or now
        last_detected_at = payload.pop("last_detected_at", None) or first_detected_at

        verified_at = now if data.status == EventStatus.VERIFIED else None
        resolved_at = now if data.status == EventStatus.RESOLVED else None

        location = (
            WKTElement(f"POINT({data.longitude} {data.latitude})", srid=4326)
            if (data.longitude is not None and data.latitude is not None)
            else None
        )

        event = Event(
            **payload,
            first_detected_at=first_detected_at,
            last_detected_at=last_detected_at,
            verified_at=verified_at,
            resolved_at=resolved_at,
            extra_metadata=extra_metadata,
            location=location,
        )
        event = await self.repo.create(event)
        await self._session.commit()
        await self._session.refresh(event)
        await self._publisher.publish_event_created(event)
        return event

    async def update_event(self, event_id: uuid.UUID, data: EventUpdate) -> Event:
        event = await self.get_event(event_id)
        update_data = data.model_dump(exclude_unset=True)

        if "bus_id" in update_data and update_data["bus_id"] is not None:
            bus = await self._bus_repo.get_by_id(update_data["bus_id"])
            if bus is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Bus {update_data['bus_id']} does not exist",
                )

        if "camera_id" in update_data and update_data["camera_id"] is not None:
            camera = await self._camera_repo.get_by_id(update_data["camera_id"])
            if camera is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Camera {update_data['camera_id']} does not exist",
                )

        # Lifecycle tracking
        now = datetime.now(timezone.utc)
        new_status = update_data.get("status")
        if new_status == EventStatus.VERIFIED and event.verified_at is None:
            event.verified_at = now
        elif new_status == EventStatus.RESOLVED and event.resolved_at is None:
            event.resolved_at = now

        # Update PostGIS geometry if coordinates changed
        new_lat = update_data.get("latitude")
        new_lon = update_data.get("longitude")
        if new_lat is not None or new_lon is not None:
            lat = new_lat if new_lat is not None else event.latitude
            lon = new_lon if new_lon is not None else event.longitude
            event.location = (
                WKTElement(f"POINT({lon} {lat})", srid=4326)
                if (lon is not None and lat is not None)
                else None
            )

        if "metadata" in update_data:
            event.extra_metadata = update_data.pop("metadata")

        event = await self.repo.update(event, update_data)
        await self._session.commit()
        await self._session.refresh(event)
        await self._publisher.publish_event_updated(event)
        return event
