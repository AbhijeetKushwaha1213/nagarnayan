"""
Detection routes — API for raw AI detection observations.

POST /api/v1/detections
GET  /api/v1/detections
GET  /api/v1/detections/{detection_id}
"""

from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.detection import DetectionCreate, DetectionResponse
from app.services.detection import DetectionService

router = APIRouter(prefix="/detections", tags=["detections"])


def _get_service(session: AsyncSession = Depends(get_db)) -> DetectionService:
    return DetectionService(session)


@router.post(
    "",
    response_model=DetectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a raw AI detection",
)
async def create_detection(
    data: DetectionCreate,
    service: DetectionService = Depends(_get_service),
) -> DetectionResponse:
    """Record an AI observation from a bus-mounted camera."""
    return await service.create_detection(data)


@router.get(
    "",
    response_model=list[DetectionResponse],
    summary="List AI detections",
)
async def list_detections(
    bus_id: uuid.UUID | None = Query(None, description="Filter by bus ID"),
    camera_id: uuid.UUID | None = Query(None, description="Filter by camera ID"),
    stream_id: uuid.UUID | None = Query(None, description="Filter by stream ID"),
    detection_type: str | None = Query(None, description="Filter by detection type"),
    event_id: uuid.UUID | None = Query(None, description="Filter by associated event ID"),
    from_timestamp: datetime | None = Query(None, description="Filter detections after or at this timestamp"),
    to_timestamp: datetime | None = Query(None, description="Filter detections before or at this timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    service: DetectionService = Depends(_get_service),
) -> list[DetectionResponse]:
    """List detections matching the given filters."""
    return await service.list_detections(
        bus_id=bus_id,
        camera_id=camera_id,
        stream_id=stream_id,
        detection_type=detection_type,
        event_id=event_id,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{detection_id}",
    response_model=DetectionResponse,
    summary="Get detection by ID",
)
async def get_detection(
    detection_id: uuid.UUID,
    service: DetectionService = Depends(_get_service),
) -> DetectionResponse:
    """Retrieve details for a single detection."""
    return await service.get_detection(detection_id)
