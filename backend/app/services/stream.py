"""
Stream service — business logic for Stream operations.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stream import Stream
from app.repositories.camera import CameraRepository
from app.repositories.stream import StreamRepository
from app.schemas.stream import StreamCreate, StreamUpdate


class StreamService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = StreamRepository(session)
        self._camera_repo = CameraRepository(session)
        self._session = session

    async def list_streams(
        self,
        camera_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Stream]:
        if camera_id is not None:
            return await self.repo.get_by_camera_id(camera_id)
        return await self.repo.get_all(limit=limit, offset=offset)

    async def get_stream(self, stream_id: uuid.UUID) -> Stream:
        stream = await self.repo.get_by_id(stream_id)
        if stream is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stream {stream_id} not found",
            )
        return stream

    async def create_stream(self, data: StreamCreate) -> Stream:
        # Validate that the referenced camera exists
        camera = await self._camera_repo.get_by_id(data.camera_id)
        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Camera {data.camera_id} does not exist",
            )
        stream = Stream(**data.model_dump())
        stream = await self.repo.create(stream)
        await self._session.commit()
        await self._session.refresh(stream)
        return stream

    async def update_stream(self, stream_id: uuid.UUID, data: StreamUpdate) -> Stream:
        stream = await self.get_stream(stream_id)
        update_data = data.model_dump(exclude_unset=True)
        stream = await self.repo.update(stream, update_data)
        await self._session.commit()
        await self._session.refresh(stream)
        return stream

    async def delete_stream(self, stream_id: uuid.UUID) -> None:
        stream = await self.get_stream(stream_id)
        await self.repo.delete(stream)
        await self._session.commit()
