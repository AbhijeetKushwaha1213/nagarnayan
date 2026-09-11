"""
Camera routes — CRUD API for Camera entities.

GET    /api/v1/cameras
GET    /api/v1/cameras/{camera_id}
POST   /api/v1/cameras
PATCH  /api/v1/cameras/{camera_id}
DELETE /api/v1/cameras/{camera_id}
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate
from app.services.camera import CameraService

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _get_service(session: AsyncSession = Depends(get_db)) -> CameraService:
    return CameraService(session)


@router.get("", response_model=list[CameraResponse], summary="List cameras")
async def list_cameras(
    bus_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    service: CameraService = Depends(_get_service),
) -> list[CameraResponse]:
    """List cameras. Optionally filter by ?bus_id=<uuid>."""
    return await service.list_cameras(bus_id=bus_id, limit=limit, offset=offset)


@router.get(
    "/{camera_id}", response_model=CameraResponse, summary="Get camera by ID"
)
async def get_camera(
    camera_id: uuid.UUID,
    service: CameraService = Depends(_get_service),
) -> CameraResponse:
    return await service.get_camera(camera_id)


@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new camera",
)
async def create_camera(
    data: CameraCreate,
    service: CameraService = Depends(_get_service),
) -> CameraResponse:
    return await service.create_camera(data)


@router.patch(
    "/{camera_id}", response_model=CameraResponse, summary="Update a camera"
)
async def update_camera(
    camera_id: uuid.UUID,
    data: CameraUpdate,
    service: CameraService = Depends(_get_service),
) -> CameraResponse:
    return await service.update_camera(camera_id, data)


@router.delete(
    "/{camera_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a camera",
    response_class=Response,
)
async def delete_camera(
    camera_id: uuid.UUID,
    service: CameraService = Depends(_get_service),
) -> Response:
    await service.delete_camera(camera_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
