"""Bus repository — database access for Bus entities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bus import Bus
from app.repositories.base import BaseRepository


class BusRepository(BaseRepository[Bus]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Bus, session)

    async def get_by_bus_number(self, bus_number: str) -> Bus | None:
        result = await self.session.execute(
            select(Bus).where(Bus.bus_number == bus_number)
        )
        return result.scalar_one_or_none()
