"""
Detection service — business logic for raw AI detections.
"""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detection import Detection
from app.repositories.bus import BusRepository
from app.repositories.camera import CameraRepository
from app.repositories.detection import DetectionRepository
from app.repositories.event import EventRepository
from app.repositories.stream import StreamRepository
from app.schemas.detection import DetectionCreate
from app.services.alert import AlertService
from app.services.event_correlation import EventCorrelationService
from app.services.severity import SeverityService
from app.websocket.publisher import WebSocketPublisher, publisher as default_publisher


class DetectionService:
    def __init__(
        self,
        session: AsyncSession,
        correlation_service: EventCorrelationService | None = None,
        severity_service: SeverityService | None = None,
        alert_service: AlertService | None = None,
        publisher: WebSocketPublisher | None = None,
    ) -> None:
        self.repo = DetectionRepository(session)
        self._bus_repo = BusRepository(session)
        self._camera_repo = CameraRepository(session)
        self._stream_repo = StreamRepository(session)
        self._event_repo = EventRepository(session)
        self._correlation_service = (
            correlation_service
            if correlation_service is not None
            else EventCorrelationService(session)
        )
        self._severity_service = (
            severity_service
            if severity_service is not None
            else SeverityService()
        )
        self._alert_service = (
            alert_service
            if alert_service is not None
            else AlertService(session)
        )
        self._publisher = publisher if publisher is not None else default_publisher
        self._session = session

    async def list_detections(
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
        return await self.repo.list(
            bus_id=bus_id,
            camera_id=camera_id,
            stream_id=stream_id,
            detection_type=detection_type,
            event_id=event_id,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            limit=limit,
            offset=offset,
        )

    async def get_detection(self, detection_id: uuid.UUID) -> Detection:
        detection = await self.repo.get_by_id(detection_id)
        if detection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detection {detection_id} not found",
            )
        return detection

    async def create_detection(self, data: DetectionCreate) -> Detection:
        # Validate that the referenced bus exists
        bus = await self._bus_repo.get_by_id(data.bus_id)
        if bus is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Bus {data.bus_id} does not exist",
            )

        # Validate that the referenced camera exists
        camera = await self._camera_repo.get_by_id(data.camera_id)
        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Camera {data.camera_id} does not exist",
            )

        # Validate that the camera belongs to the referenced bus
        if camera.bus_id != data.bus_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Camera {data.camera_id} is mounted on bus {camera.bus_id}, not {data.bus_id}",
            )

        # If a stream_id is supplied, verify it exists and belongs to the camera
        if data.stream_id is not None:
            stream = await self._stream_repo.get_by_id(data.stream_id)
            if stream is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Stream {data.stream_id} does not exist",
                )
            if stream.camera_id != data.camera_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Stream {data.stream_id} belongs to camera {stream.camera_id}, not {data.camera_id}",
                )

        # If an event_id is supplied, verify it exists
        if data.event_id is not None:
            event = await self._event_repo.get_by_id(data.event_id)
            if event is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Event {data.event_id} does not exist",
                )

        # Idempotency / Retry guard: return existing detection if duplicate frame observation is retried
        if data.frame_reference:
            existing = await self.repo.find_duplicate(
                camera_id=data.camera_id,
                frame_reference=data.frame_reference,
                detection_type=data.detection_type,
            )
            if existing is not None:
                return existing

        payload = data.model_dump()
        extra_metadata = payload.pop("metadata", {})
        location = (
            WKTElement(f"POINT({data.longitude} {data.latitude})", srid=4326)
            if (data.longitude is not None and data.latitude is not None)
            else None
        )

        detection = Detection(
            **payload,
            extra_metadata=extra_metadata,
            location=location,
        )
        detection = await self.repo.create(detection)
        await self._session.flush()

        # Automatic Event correlation & deduplication (when event_id is not explicitly provided)
        correlated_event = None
        is_new_event = False
        if data.event_id is None:
            correlated_event = await self._correlation_service.correlate_and_link(detection)
            is_new_event = getattr(correlated_event, "_is_new", False) if correlated_event else False
        else:
            correlated_event = await self._event_repo.get_by_id(data.event_id)
            is_new_event = False

        # Evaluate and update Event severity based on Phase 6 Severity Engine
        if correlated_event is not None:
            self._severity_service.evaluate_and_update_event_severity(correlated_event)

        # Automatic Alert synthesis when the Event requires municipal attention
        created_alert = None
        if correlated_event is not None:
            alert_result = await self._alert_service.process_event_for_alert(correlated_event)
            if alert_result is not None and getattr(alert_result, "_is_new", False):
                created_alert = alert_result

        # Commit database transaction first (Step 8: strict transaction rule)
        await self._session.commit()
        await self._session.refresh(detection)

        # Post-commit WebSocket publishing in strict logical order (Step 8 & 17)
        # 1. Publish Event notification first (allows dashboard to establish event context)
        if correlated_event is not None:
            if is_new_event:
                await self._publisher.publish_event_created(correlated_event)
            else:
                await self._publisher.publish_event_updated(correlated_event)

        # 2. Publish Alert notification second (if a new alert was synthesized)
        if created_alert is not None:
            await self._publisher.publish_alert_created(created_alert)

        return detection
