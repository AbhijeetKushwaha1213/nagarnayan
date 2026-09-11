"""Camera repository — database access for Camera entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera
from app.repositories.base import BaseRepository


class CameraRepository(BaseRepository[Camera]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Camera, session)

    async def get_by_bus_id(self, bus_id: uuid.UUID) -> list[Camera]:
        result = await self.session.execute(
            select(Camera).where(Camera.bus_id == bus_id)
        )
        return list(result.scalars().all())
