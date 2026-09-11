"""
Urban Event Correlation Engine.

Maps incoming raw AI detections into persistent, real-world municipal issues (Urban Events).
Correlates spatially and temporally compatible detections using PostGIS ST_DWithin and
time window boundaries. Strictly adheres to the zero-fabricated GPS policy and concurrency safety.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.detection import Detection
from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.repositories.event import EventRepository

logger = logging.getLogger("nagar_nayan.correlation")

# Mapping of AI detection types to municipal EventTypes
DETECTION_TYPE_TO_EVENT_TYPE: dict[str, EventType] = {
    # Road Infrastructure Defects
    "POTHOLE": EventType.POTHOLE,
    "DAMAGED_ROAD": EventType.DAMAGED_ROAD,
    "ROAD_DAMAGE": EventType.DAMAGED_ROAD,
    "WATERLOGGING": EventType.WATERLOGGING,
    "FLOODING": EventType.WATERLOGGING,
    "MISSING_DIVIDER": EventType.MISSING_DIVIDER,
    "DIVIDER_DAMAGE": EventType.MISSING_DIVIDER,
    "MISSING_ZEBRA_CROSSING": EventType.MISSING_ZEBRA_CROSSING,
    "MISSING_SIGNBOARD": EventType.MISSING_SIGNBOARD,
    "TRAFFIC_CONGESTION": EventType.TRAFFIC_CONGESTION,
    "CONGESTION": EventType.TRAFFIC_CONGESTION,

    # Object categories (eligible for peer correlation, but distinct from defects)
    "VEHICLE": EventType.VEHICLE,
    "CAR": EventType.VEHICLE,
    "BUS": EventType.VEHICLE,
    "TRUCK": EventType.VEHICLE,
    "MOTORCYCLE": EventType.VEHICLE,
    "BICYCLE": EventType.VEHICLE,
    "PEDESTRIAN": EventType.PEDESTRIAN,
    "PERSON": EventType.PEDESTRIAN,
    "OTHER": EventType.OTHER,
}


def is_valid_location(latitude: float | None, longitude: float | None) -> bool:
    """Validate that both latitude and longitude are present and within geographic bounds."""
    if latitude is None or longitude is None:
        return False
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (ValueError, TypeError):
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return True


def compute_spatial_grid_cell(
    latitude: float,
    longitude: float,
    grid_size_degrees: float = 0.001,
) -> tuple[int, int]:
    """
    Map WGS84 geographic coordinates to discrete integer grid cell coordinates.
    A resolution of 0.001 degrees corresponds to ~111 meters in latitude and ~108 meters in
    longitude at 13°N (Bangalore), establishing localized neighborhood buckets.
    """
    grid_lat = int(math.floor(latitude / grid_size_degrees))
    grid_lon = int(math.floor(longitude / grid_size_degrees))
    return grid_lat, grid_lon


def get_spatial_lock_keys(
    event_type: EventType,
    latitude: float,
    longitude: float,
    radius_meters: float = 50.0,
    grid_size_degrees: float = 0.001,
) -> list[str]:
    """
    Derive deterministic, sorted transaction advisory lock keys scoped to event type and spatial neighborhood.

    Design & Concurrency Guarantees:
      1. Event Type Scoping: Keys are prefixed with `event_correlation:{event_type.value}:...`, ensuring
         different issue types (e.g. POTHOLE vs WATERLOGGING) never serialize each other.
      2. Spatial Grid Scoping: Disjoint geographic regions produce disjoint lock keys, allowing detections
         in different parts of the city to be processed in parallel.
      3. Boundary Overlap Protection: Computes the bounding box of radius_meters around (latitude, longitude)
         and covers all intersecting grid cells. Because any two detections within distance <= radius_meters
         will overlap on at least one common grid cell, both transactions will request a lock on that common cell.
      4. Deadlock Freedom: Lock keys are returned in strictly sorted lexicographical order. When multiple
         transactions acquire locks in the same canonical order, PostgreSQL cannot deadlock.
    """
    delta_lat = radius_meters / 111320.0
    rad_lat = math.radians(latitude)
    cos_lat = math.cos(rad_lat) if abs(math.cos(rad_lat)) > 1e-6 else 1.0
    delta_lon = radius_meters / (111320.0 * cos_lat)

    min_grid_lat = int(math.floor((latitude - delta_lat) / grid_size_degrees))
    max_grid_lat = int(math.floor((latitude + delta_lat) / grid_size_degrees))
    min_grid_lon = int(math.floor((longitude - delta_lon) / grid_size_degrees))
    max_grid_lon = int(math.floor((longitude + delta_lon) / grid_size_degrees))

    keys: set[str] = set()
    for glat in range(min_grid_lat, max_grid_lat + 1):
        for glon in range(min_grid_lon, max_grid_lon + 1):
            keys.add(f"event_correlation:{event_type.value}:{glat}:{glon}")

    return sorted(keys)


class EventCorrelationService:
    """Service orchestrating detection-to-event spatial-temporal correlation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._event_repo = EventRepository(session)

    @staticmethod
    def resolve_event_type(detection_type: str) -> EventType | None:
        """
        Resolve a detection_type string to a supported EventType.
        Returns None for unmapped types.
        """
        normalized = detection_type.strip().upper()
        if normalized in DETECTION_TYPE_TO_EVENT_TYPE:
            return DETECTION_TYPE_TO_EVENT_TYPE[normalized]

        try:
            return EventType(normalized)
        except ValueError:
            return None

    async def correlate_and_link(
        self,
        detection: Detection,
        radius_meters: float | None = None,
        time_window_seconds: int | None = None,
    ) -> Event | None:
        """
        Correlate a newly persisted Detection with an existing active Event, or create a new Event.

        Rules:
          1. Unmapped detection types return None (no event synthesized).
          2. GPS Rule: If latitude or longitude is missing/null/invalid, do NOT fabricate coordinates
             and do NOT create a spatially correlated event. Return None.
          3. SENSING MATCH: Query active, open events of the EXACT SAME event_type within
             configured spatial radius (ST_DWithin) and temporal window (last_detected_at).
          4. CONCURRENCY: Uses row-level locking (with_for_update) and transaction-scoped advisory
             locks on PostgreSQL scoped to event type and spatial neighborhood to prevent duplicate
             event creation from concurrent observations.
          5. AGGREGATION: When attaching to an existing event, update last_detected_at, preserve
             first_detected_at, and compute deterministic running average confidence (bounded <= 1.0).
          6. SYNTHESIS: When no active candidate matches, create a new Urban Event in DETECTED state
             using the database schema-safe default severity (EventSeverity.MEDIUM).
             Urban event correlation does not calculate or classify severity.

        Returns:
            The associated Event instance, or None if detection could not be correlated.
        """
        # 1. Resolve event type
        event_type = self.resolve_event_type(detection.detection_type)
        if event_type is None:
            logger.info(
                "Detection %s has unmapped detection_type=%r; skipping event correlation.",
                detection.id,
                detection.detection_type,
            )
            return None

        # 2. Strict GPS check: Never fabricate coordinates
        if not is_valid_location(detection.latitude, detection.longitude):
            logger.info(
                "Detection %s missing/invalid GPS (lat=%s, lon=%s); skipping spatial event correlation.",
                detection.id,
                detection.latitude,
                detection.longitude,
            )
            return None

        radius = float(
            radius_meters
            if radius_meters is not None
            else getattr(settings, "EVENT_CORRELATION_RADIUS_METERS", 50.0)
        )
        time_window = int(
            time_window_seconds
            if time_window_seconds is not None
            else getattr(settings, "EVENT_CORRELATION_WINDOW_SECONDS", 300)
        )

        # 3. Concurrency guard: Acquire transaction-scoped advisory locks on PostgreSQL
        # Serializes concurrent event creation for the same event_type within the spatial neighborhood
        if self._session.bind and getattr(self._session.bind.dialect, "name", None) == "postgresql":
            try:
                lock_keys = get_spatial_lock_keys(
                    event_type=event_type,
                    latitude=float(detection.latitude),
                    longitude=float(detection.longitude),
                    radius_meters=radius,
                )
                for lk in lock_keys:
                    await self._session.execute(
                        select(func.pg_advisory_xact_lock(func.hashtext(lk)))
                    )
            except Exception as lock_err:
                logger.debug("Advisory transaction lock skipped or unhandled: %s", lock_err)

        # 4. Search for candidate active event within spatial radius and temporal window
        matched_event = await self._event_repo.find_nearby_active_event(
            event_type=event_type,
            latitude=float(detection.latitude),
            longitude=float(detection.longitude),
            detection_time=detection.detected_at,
            radius_meters=radius,
            time_window_seconds=time_window,
            for_update=True,
        )

        # 5. Existing Event Found: Correlate and Aggregate
        if matched_event is not None:
            # Preserve first_detected_at, update last_detected_at to most recent observation
            matched_event.last_detected_at = max(
                matched_event.last_detected_at, detection.detected_at
            )

            # Deterministic running weighted average confidence aggregation:
            # C_{n+1} = round((C_n * n + c_new) / (n + 1), 4), strictly in [0.0, 1.0]
            metadata = dict(matched_event.extra_metadata or {})
            obs_count = int(metadata.get("detection_count", 1))
            new_confidence = round(
                ((matched_event.confidence * obs_count) + float(detection.confidence))
                / (obs_count + 1),
                4,
            )
            matched_event.confidence = min(1.0, max(0.0, new_confidence))

            # Aggregate metadata and unique reporting sensing sources
            metadata["detection_count"] = obs_count + 1
            metadata["last_detection_id"] = str(detection.id)
            reporting_buses = list(metadata.get("reporting_buses", []))
            bus_id_str = str(detection.bus_id)
            if bus_id_str not in reporting_buses:
                reporting_buses.append(bus_id_str)
            metadata["reporting_buses"] = reporting_buses
            matched_event.extra_metadata = metadata

            # Link detection to existing event
            detection.event_id = matched_event.id
            matched_event._is_new = False

            logger.info(
                "Correlated Detection %s -> existing Event %s (%s, count=%d, conf=%.4f, buses=%s)",
                detection.id,
                matched_event.id,
                event_type.value,
                obs_count + 1,
                matched_event.confidence,
                reporting_buses,
            )
            return matched_event

        # 6. No Candidate Found: Synthesize New Urban Event
        # Severity is initialized to the schema default (MEDIUM); Phase 5 correlation does NOT calculate severity.
        metadata: dict[str, Any] = {
            "source": "automated_detection",
            "initial_detection_id": str(detection.id),
            "detection_count": 1,
            "reporting_buses": [str(detection.bus_id)],
        }
        if detection.extra_metadata:
            metadata["initial_ai_metadata"] = detection.extra_metadata

        new_event = Event(
            id=uuid.uuid4(),
            event_type=event_type,
            severity=EventSeverity.MEDIUM,
            status=EventStatus.DETECTED,
            latitude=detection.latitude,
            longitude=detection.longitude,
            location=detection.location,
            confidence=round(float(detection.confidence), 4),
            first_detected_at=detection.detected_at,
            last_detected_at=detection.detected_at,
            bus_id=detection.bus_id,
            camera_id=detection.camera_id,
            evidence_reference=detection.frame_reference,
            extra_metadata=metadata,
        )

        new_event = await self._event_repo.create(new_event)
        await self._session.flush()

        detection.event_id = new_event.id
        new_event._is_new = True

        logger.info(
            "Synthesized new Urban Event %s (%s, conf=%.4f) from Detection %s",
            new_event.id,
            event_type.value,
            new_event.confidence,
            detection.id,
        )
        return new_event
