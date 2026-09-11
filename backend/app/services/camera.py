"""
Camera service — business logic for Camera operations.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera
from app.repositories.bus import BusRepository
from app.repositories.camera import CameraRepository
from app.schemas.camera import CameraCreate, CameraUpdate


class CameraService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CameraRepository(session)
        self._bus_repo = BusRepository(session)
        self._session = session

    async def list_cameras(
        self,
        bus_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Camera]:
        if bus_id is not None:
            return await self.repo.get_by_bus_id(bus_id)
        return await self.repo.get_all(limit=limit, offset=offset)

    async def get_camera(self, camera_id: uuid.UUID) -> Camera:
        camera = await self.repo.get_by_id(camera_id)
        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found",
            )
        return camera

    async def create_camera(self, data: CameraCreate) -> Camera:
        # Validate that the referenced bus exists
        bus = await self._bus_repo.get_by_id(data.bus_id)
        if bus is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Bus {data.bus_id} does not exist",
            )
        camera = Camera(**data.model_dump())
        camera = await self.repo.create(camera)
        await self._session.commit()
        await self._session.refresh(camera)
        return camera

    async def update_camera(self, camera_id: uuid.UUID, data: CameraUpdate) -> Camera:
        camera = await self.get_camera(camera_id)
        update_data = data.model_dump(exclude_unset=True)
        camera = await self.repo.update(camera, update_data)
        await self._session.commit()
        await self._session.refresh(camera)
        return camera

    async def delete_camera(self, camera_id: uuid.UUID) -> None:
        camera = await self.get_camera(camera_id)
        await self.repo.delete(camera)
        await self._session.commit()
