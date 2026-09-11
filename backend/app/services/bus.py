"""
Bus service — business logic for Bus operations.

Responsibilities:
  - Validate business rules (e.g. unique bus_number)
  - Orchestrate repository calls
  - Raise HTTP-appropriate exceptions

Database queries live in BusRepository, not here.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bus import Bus
from app.repositories.bus import BusRepository
from app.schemas.bus import BusCreate, BusUpdate


class BusService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = BusRepository(session)
        self._session = session

    async def list_buses(self, limit: int = 100, offset: int = 0) -> list[Bus]:
        return await self.repo.get_all(limit=limit, offset=offset)

    async def get_bus(self, bus_id: uuid.UUID) -> Bus:
        bus = await self.repo.get_by_id(bus_id)
        if bus is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bus {bus_id} not found",
            )
        return bus

    async def create_bus(self, data: BusCreate) -> Bus:
        existing = await self.repo.get_by_bus_number(data.bus_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bus number '{data.bus_number}' already exists",
            )
        bus = Bus(**data.model_dump())
        bus = await self.repo.create(bus)
        await self._session.commit()
        await self._session.refresh(bus)
        return bus

    async def update_bus(self, bus_id: uuid.UUID, data: BusUpdate) -> Bus:
        bus = await self.get_bus(bus_id)
        update_data = data.model_dump(exclude_unset=True)
        if "bus_number" in update_data:
            existing = await self.repo.get_by_bus_number(update_data["bus_number"])
            if existing and existing.id != bus_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Bus number '{update_data['bus_number']}' already exists",
                )
        bus = await self.repo.update(bus, update_data)
        await self._session.commit()
        await self._session.refresh(bus)
        return bus

    async def delete_bus(self, bus_id: uuid.UUID) -> None:
        bus = await self.get_bus(bus_id)
        await self.repo.delete(bus)
        await self._session.commit()
