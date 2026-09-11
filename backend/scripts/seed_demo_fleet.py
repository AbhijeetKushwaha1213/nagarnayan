"""
Nagar Nayan — Idempotent Demo Fleet Seeding Script.

Creates or updates deterministic demo records for:
  - 1 Bus: 00000000-0000-0000-0000-000000000001
  - 1 Front Camera: 00000000-0000-0000-0000-000000000001
  - 1 RTSP Stream: 00000000-0000-0000-0000-000000000001

Guarantees:
  - Matching IDs for AI service configuration
  - Idempotent execution (can be run repeatedly without duplicating records)
  - Clean connection teardown
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import sys
import uuid

from sqlalchemy import select

from app.core.database import _get_engine, _get_session_factory
from app.models.bus import Bus, BusStatus
from app.models.camera import Camera, CameraStatus, CameraType
from app.models.stream import Stream, StreamProtocol, StreamStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo_fleet")

DEMO_BUS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_CAMERA_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_STREAM_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_RTSP_URL = "rtsp://localhost:8554/bus/front"


async def seed_demo_fleet() -> dict[str, str]:
    factory = _get_session_factory()
    if factory is None:
        raise RuntimeError("Database session factory could not be initialized. Check DATABASE_URL.")

    engine = _get_engine()
    created_or_updated: dict[str, str] = {}

    try:
        async with factory() as session:
            # 1. Seed or update Bus
            bus_stmt = select(Bus).where(Bus.id == DEMO_BUS_ID)
            bus = (await session.execute(bus_stmt)).scalar_one_or_none()

            if bus is None:
                bus = Bus(
                    id=DEMO_BUS_ID,
                    bus_number="DL-01-NN-1001",
                    route_id="ROUTE-DELHI-01",
                    status=BusStatus.active,
                )
                session.add(bus)
                await session.flush()
                logger.info("Created demo Bus: %s (id=%s)", bus.bus_number, bus.id)
                created_or_updated["bus"] = f"Created {bus.id} ({bus.bus_number})"
            else:
                bus.status = BusStatus.active
                bus.bus_number = "DL-01-NN-1001"
                bus.route_id = "ROUTE-DELHI-01"
                logger.info("Existing demo Bus verified: %s (id=%s)", bus.bus_number, bus.id)
                created_or_updated["bus"] = f"Verified {bus.id} ({bus.bus_number})"

            # 2. Seed or update Camera
            cam_stmt = select(Camera).where(Camera.id == DEMO_CAMERA_ID)
            camera = (await session.execute(cam_stmt)).scalar_one_or_none()

            if camera is None:
                camera = Camera(
                    id=DEMO_CAMERA_ID,
                    bus_id=DEMO_BUS_ID,
                    camera_type=CameraType.front,
                    status=CameraStatus.active,
                )
                session.add(camera)
                await session.flush()
                logger.info("Created demo Camera: type=%s, bus_id=%s (id=%s)", camera.camera_type, camera.bus_id, camera.id)
                created_or_updated["camera"] = f"Created {camera.id} ({camera.camera_type})"
            else:
                camera.status = CameraStatus.active
                camera.bus_id = DEMO_BUS_ID
                camera.camera_type = CameraType.front
                logger.info("Existing demo Camera verified: id=%s", camera.id)
                created_or_updated["camera"] = f"Verified {camera.id} ({camera.camera_type})"

            # 3. Seed or update Stream
            stream_stmt = select(Stream).where(Stream.id == DEMO_STREAM_ID)
            stream = (await session.execute(stream_stmt)).scalar_one_or_none()

            if stream is None:
                stream = Stream(
                    id=DEMO_STREAM_ID,
                    camera_id=DEMO_CAMERA_ID,
                    stream_url=DEMO_RTSP_URL,
                    protocol=StreamProtocol.rtsp,
                    status=StreamStatus.active,
                    started_at=datetime.now(timezone.utc),
                )
                session.add(stream)
                await session.flush()
                logger.info("Created demo Stream: %s (id=%s)", stream.stream_url, stream.id)
                created_or_updated["stream"] = f"Created {stream.id} ({stream.stream_url})"
            else:
                stream.status = StreamStatus.active
                stream.camera_id = DEMO_CAMERA_ID
                stream.stream_url = DEMO_RTSP_URL
                logger.info("Existing demo Stream verified: id=%s", stream.id)
                created_or_updated["stream"] = f"Verified {stream.id} ({stream.stream_url})"

            await session.commit()
            logger.info("Demo fleet seeding successfully committed to database.")

    finally:
        if engine is not None:
            await engine.dispose()

    return created_or_updated


if __name__ == "__main__":
    results = asyncio.run(seed_demo_fleet())
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("Seed complete.")
