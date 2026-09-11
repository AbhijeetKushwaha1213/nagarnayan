"""
Event routes — API for validated urban issues.

POST  /api/v1/events
GET   /api/v1/events
GET   /api/v1/events/{event_id}
PATCH /api/v1/events/{event_id}
"""

from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.event import EventSeverity, EventStatus, EventType
from app.schemas.event import (
    EventCreate,
    EventResponse,
    EventUpdate,
    GeoJSONEventFeature,
    GeoJSONEventProperties,
    GeoJSONFeatureCollection,
    GeoJSONGeometryPoint,
)
from app.services.event import EventService

router = APIRouter(prefix="/events", tags=["events"])


def _get_service(session: AsyncSession = Depends(get_db)) -> EventService:
    return EventService(session)


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a validated urban event",
)
async def create_event(
    data: EventCreate,
    service: EventService = Depends(_get_service),
) -> EventResponse:
    """Register a new validated urban event."""
    return await service.create_event(data)


@router.get(
    "",
    response_model=list[EventResponse],
    summary="List urban events",
)
async def list_events(
    event_type: EventType | None = Query(None, description="Filter by event type"),
    status: EventStatus | None = Query(None, description="Filter by status"),
    severity: EventSeverity | None = Query(None, description="Filter by severity"),
    bus_id: uuid.UUID | None = Query(None, description="Filter by reporting bus ID"),
    camera_id: uuid.UUID | None = Query(None, description="Filter by reporting camera ID"),
    from_timestamp: datetime | None = Query(None, description="Filter events after or at this timestamp"),
    to_timestamp: datetime | None = Query(None, description="Filter events before or at this timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    service: EventService = Depends(_get_service),
) -> list[EventResponse]:
    """List urban events matching the given criteria."""
    return await service.list_events(
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


@router.get(
    "/geojson",
    response_model=GeoJSONFeatureCollection,
    summary="Get events as GeoJSON FeatureCollection",
)
async def get_events_geojson(
    event_type: EventType | None = Query(None, description="Filter by event type"),
    status: EventStatus | None = Query(None, description="Filter by status"),
    severity: EventSeverity | None = Query(None, description="Filter by severity"),
    bus_id: uuid.UUID | None = Query(None, description="Filter by reporting bus ID"),
    camera_id: uuid.UUID | None = Query(None, description="Filter by reporting camera ID"),
    from_timestamp: datetime | None = Query(None, description="Filter events after or at this timestamp"),
    to_timestamp: datetime | None = Query(None, description="Filter events before or at this timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    service: EventService = Depends(_get_service),
) -> GeoJSONFeatureCollection:
    """Return urban events formatted as a standard GeoJSON FeatureCollection."""
    events = await service.list_events(
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
    features: list[GeoJSONEventFeature] = []
    for ev in events:
        geom = (
            GeoJSONGeometryPoint(type="Point", coordinates=[ev.longitude, ev.latitude])
            if (ev.longitude is not None and ev.latitude is not None)
            else None
        )
        props = GeoJSONEventProperties(
            event_id=ev.id,
            event_type=ev.event_type,
            status=ev.status,
            severity=ev.severity,
            confidence=ev.confidence,
            detected_at=ev.first_detected_at,
        )
        features.append(GeoJSONEventFeature(type="Feature", geometry=geom, properties=props))

    return GeoJSONFeatureCollection(type="FeatureCollection", features=features)


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event by ID",
)
async def get_event(
    event_id: uuid.UUID,
    service: EventService = Depends(_get_service),
) -> EventResponse:
    """Retrieve details for a single urban event."""
    return await service.get_event(event_id)


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update an urban event",
)
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    service: EventService = Depends(_get_service),
) -> EventResponse:
    """Update event status, severity, coordinates, or lifecycle timestamps."""
    return await service.update_event(event_id, data)
