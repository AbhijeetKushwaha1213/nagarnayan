"""Event repository — database queries for Event entities."""

from __future__ import annotations

from datetime import datetime, timedelta
import uuid

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import (
    ACTIVE_EVENT_STATUSES,
    Event,
    EventSeverity,
    EventStatus,
    EventType,
)
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Event, session)

    async def list(
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
        query = select(Event)
        if event_type is not None:
            query = query.where(Event.event_type == event_type)
        if status is not None:
            query = query.where(Event.status == status)
        if severity is not None:
            query = query.where(Event.severity == severity)
        if bus_id is not None:
            query = query.where(Event.bus_id == bus_id)
        if camera_id is not None:
            query = query.where(Event.camera_id == camera_id)
        if from_timestamp is not None:
            query = query.where(Event.first_detected_at >= from_timestamp)
        if to_timestamp is not None:
            query = query.where(Event.last_detected_at <= to_timestamp)

        query = query.order_by(Event.last_detected_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_type(
        self,
        event_type: EventType,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        return await self.list(event_type=event_type, limit=limit, offset=offset)

    async def list_by_status(
        self,
        status: EventStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        return await self.list(status=status, limit=limit, offset=offset)

    async def list_by_severity(
        self,
        severity: EventSeverity,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        return await self.list(severity=severity, limit=limit, offset=offset)

    async def list_by_bus(
        self,
        bus_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        return await self.list(bus_id=bus_id, limit=limit, offset=offset)

    async def list_by_camera(
        self,
        camera_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        return await self.list(camera_id=camera_id, limit=limit, offset=offset)

    async def find_nearby_active_event(
        self,
        event_type: EventType,
        latitude: float,
        longitude: float,
        detection_time: datetime,
        radius_meters: float = 50.0,
        time_window_seconds: int = 300,
        for_update: bool = False,
    ) -> Event | None:
        """
        Find an active, open Event of compatible type within radius_meters and time_window_seconds.

        Temporal Rule:
          - Enforces |detection_time - Event.last_detected_at| <= time_window_seconds.
          - For normal chronological arrivals: (detection_time - Event.last_detected_at) <= time_window.
          - Safely allows out-of-order timestamps within window without matching overly broad future bounds.
        Spatial Rule:
          - Uses PostGIS ST_DWithin on WGS84 coordinates cast to Geography for accurate metric distance.
        Status Rule:
          - Only searches events in ACTIVE_EVENT_STATUSES (excludes terminal RESOLVED/REJECTED).
        """
        min_time = detection_time - timedelta(seconds=time_window_seconds)
        max_time = detection_time + timedelta(seconds=time_window_seconds)

        detection_point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        point_geog = cast(detection_point, Geography)
        location_geog = cast(Event.location, Geography)

        query = (
            select(Event)
            .where(
                Event.event_type == event_type,
                Event.status.in_(ACTIVE_EVENT_STATUSES),
                Event.last_detected_at >= min_time,
                Event.last_detected_at <= max_time,
                Event.location.isnot(None),
                func.ST_DWithin(location_geog, point_geog, radius_meters),
            )
            .order_by(
                func.ST_Distance(location_geog, point_geog).asc(),
                Event.last_detected_at.desc(),
            )
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()

        result = await self.session.execute(query)
        return result.scalars().first()

    async def find_active_bus_camera_event(
        self,
        event_type: EventType,
        bus_id: uuid.UUID,
        camera_id: uuid.UUID,
        detection_time: datetime,
        time_window_seconds: int = 300,
        for_update: bool = False,
    ) -> Event | None:
        """
        Non-spatial fallback: find an active, open Event of compatible type for the same
        bus and camera within time_window_seconds where coordinates are absent.
        """
        min_time = detection_time - timedelta(seconds=time_window_seconds)
        max_time = detection_time + timedelta(seconds=time_window_seconds)

        query = (
            select(Event)
            .where(
                Event.event_type == event_type,
                Event.status.notin_([EventStatus.RESOLVED, EventStatus.REJECTED]),
                Event.bus_id == bus_id,
                Event.camera_id == camera_id,
                Event.latitude.is_(None),
                Event.longitude.is_(None),
                Event.last_detected_at >= min_time,
                Event.first_detected_at <= max_time,
            )
            .order_by(Event.last_detected_at.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()

        result = await self.session.execute(query)
        return result.scalars().first()
