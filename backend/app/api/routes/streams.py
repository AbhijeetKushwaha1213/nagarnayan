"""
Stream routes — CRUD API for Stream entities.

GET    /api/v1/streams
GET    /api/v1/streams/{stream_id}
POST   /api/v1/streams
PATCH  /api/v1/streams/{stream_id}
DELETE /api/v1/streams/{stream_id}

IMPORTANT: These endpoints manage stream METADATA only.
The backend does NOT start, stop, read, or process RTSP streams.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.stream import StreamCreate, StreamResponse, StreamUpdate
from app.services.stream import StreamService

router = APIRouter(prefix="/streams", tags=["streams"])


def _get_service(session: AsyncSession = Depends(get_db)) -> StreamService:
    return StreamService(session)


@router.get("", response_model=list[StreamResponse], summary="List streams")
async def list_streams(
    camera_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    service: StreamService = Depends(_get_service),
) -> list[StreamResponse]:
    """List stream metadata. Optionally filter by ?camera_id=<uuid>."""
    return await service.list_streams(camera_id=camera_id, limit=limit, offset=offset)


@router.get(
    "/{stream_id}", response_model=StreamResponse, summary="Get stream by ID"
)
async def get_stream(
    stream_id: uuid.UUID,
    service: StreamService = Depends(_get_service),
) -> StreamResponse:
    return await service.get_stream(stream_id)


@router.post(
    "",
    response_model=StreamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register stream metadata",
)
async def create_stream(
    data: StreamCreate,
    service: StreamService = Depends(_get_service),
) -> StreamResponse:
    return await service.create_stream(data)


@router.patch(
    "/{stream_id}", response_model=StreamResponse, summary="Update stream metadata"
)
async def update_stream(
    stream_id: uuid.UUID,
    data: StreamUpdate,
    service: StreamService = Depends(_get_service),
) -> StreamResponse:
    return await service.update_stream(stream_id, data)


@router.delete(
    "/{stream_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete stream metadata",
    response_class=Response,
)
async def delete_stream(
    stream_id: uuid.UUID,
    service: StreamService = Depends(_get_service),
) -> Response:
    await service.delete_stream(stream_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
