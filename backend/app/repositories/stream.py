"""Stream repository — database access for Stream entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stream import Stream
from app.repositories.base import BaseRepository


class StreamRepository(BaseRepository[Stream]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Stream, session)

    async def get_by_camera_id(self, camera_id: uuid.UUID) -> list[Stream]:
        result = await self.session.execute(
            select(Stream).where(Stream.camera_id == camera_id)
        )
        return list(result.scalars().all())
