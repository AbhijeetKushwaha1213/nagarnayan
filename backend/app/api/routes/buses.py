"""
Bus routes — CRUD API for Bus entities.

GET    /api/v1/buses
GET    /api/v1/buses/{bus_id}
POST   /api/v1/buses
PATCH  /api/v1/buses/{bus_id}
DELETE /api/v1/buses/{bus_id}
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.bus import BusCreate, BusResponse, BusUpdate
from app.services.bus import BusService

router = APIRouter(prefix="/buses", tags=["buses"])


def _get_service(session: AsyncSession = Depends(get_db)) -> BusService:
    return BusService(session)


@router.get("", response_model=list[BusResponse], summary="List all buses")
async def list_buses(
    limit: int = 100,
    offset: int = 0,
    service: BusService = Depends(_get_service),
) -> list[BusResponse]:
    return await service.list_buses(limit=limit, offset=offset)


@router.get("/{bus_id}", response_model=BusResponse, summary="Get bus by ID")
async def get_bus(
    bus_id: uuid.UUID,
    service: BusService = Depends(_get_service),
) -> BusResponse:
    return await service.get_bus(bus_id)


@router.post(
    "",
    response_model=BusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bus",
)
async def create_bus(
    data: BusCreate,
    service: BusService = Depends(_get_service),
) -> BusResponse:
    return await service.create_bus(data)


@router.patch("/{bus_id}", response_model=BusResponse, summary="Update a bus")
async def update_bus(
    bus_id: uuid.UUID,
    data: BusUpdate,
    service: BusService = Depends(_get_service),
) -> BusResponse:
    return await service.update_bus(bus_id, data)


@router.delete(
    "/{bus_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a bus",
    response_class=Response,
)
async def delete_bus(
    bus_id: uuid.UUID,
    service: BusService = Depends(_get_service),
) -> Response:
    await service.delete_bus(bus_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
