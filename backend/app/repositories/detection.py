"""Detection repository — database queries for Detection entities."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detection import Detection
from app.repositories.base import BaseRepository


class DetectionRepository(BaseRepository[Detection]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Detection, session)

    async def list(
        self,
        bus_id: uuid.UUID | None = None,
        camera_id: uuid.UUID | None = None,
        stream_id: uuid.UUID | None = None,
        detection_type: str | None = None,
        event_id: uuid.UUID | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Detection]:
        query = select(Detection)
        if bus_id is not None:
            query = query.where(Detection.bus_id == bus_id)
        if camera_id is not None:
            query = query.where(Detection.camera_id == camera_id)
        if stream_id is not None:
            query = query.where(Detection.stream_id == stream_id)
        if detection_type is not None:
            query = query.where(Detection.detection_type == detection_type)
        if event_id is not None:
            query = query.where(Detection.event_id == event_id)
        if from_timestamp is not None:
            query = query.where(Detection.detected_at >= from_timestamp)
        if to_timestamp is not None:
            query = query.where(Detection.detected_at <= to_timestamp)

        query = query.order_by(Detection.detected_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_bus(
        self,
        bus_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Detection]:
        return await self.list(bus_id=bus_id, limit=limit, offset=offset)

    async def list_by_camera(
        self,
        camera_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Detection]:
        return await self.list(camera_id=camera_id, limit=limit, offset=offset)

    async def list_by_type(
        self,
        detection_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Detection]:
        return await self.list(detection_type=detection_type, limit=limit, offset=offset)

    async def find_duplicate(
        self,
        camera_id: uuid.UUID,
        frame_reference: str,
        detection_type: str,
    ) -> Detection | None:
        """
        Lightweight idempotency lookup: checks if a detection with the same
        (camera_id, frame_reference, detection_type) has already been ingested.
        """
        query = (
            select(Detection)
            .where(
                Detection.camera_id == camera_id,
                Detection.frame_reference == frame_reference,
                Detection.detection_type == detection_type,
            )
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

