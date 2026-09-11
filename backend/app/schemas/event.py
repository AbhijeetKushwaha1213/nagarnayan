"""Event Pydantic schemas — API request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.event import EventSeverity, EventStatus, EventType


class EventCreate(BaseModel):
    """Payload for creating a validated urban Event."""

    event_type: EventType = Field(..., description="Category of urban issue", examples=[EventType.POTHOLE])
    severity: EventSeverity = Field(EventSeverity.MEDIUM, description="Urgency / severity level")
    status: EventStatus = Field(EventStatus.DETECTED, description="Current lifecycle state")
    latitude: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Latitude between -90.0 and 90.0 (optional when GPS telemetry is absent)",
        examples=[12.9716],
    )
    longitude: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Longitude between -180.0 and 180.0 (optional when GPS telemetry is absent)",
        examples=[77.5946],
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Aggregated confidence between 0.0 and 1.0")
    first_detected_at: datetime | None = Field(None, description="Timestamp of first observation (defaults to now)")
    last_detected_at: datetime | None = Field(None, description="Timestamp of most recent observation (defaults to now)")
    bus_id: uuid.UUID | None = Field(None, description="Optional reporting bus ID")
    camera_id: uuid.UUID | None = Field(None, description="Optional reporting camera ID")
    evidence_reference: str | None = Field(None, max_length=500, description="Reference image or video evidence")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata key-value storage")


class EventUpdate(BaseModel):
    """Payload for updating an existing Event (partial updates supported)."""

    event_type: EventType | None = None
    severity: EventSeverity | None = None
    status: EventStatus | None = None
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    last_detected_at: datetime | None = None
    verified_at: datetime | None = None
    resolved_at: datetime | None = None
    bus_id: uuid.UUID | None = None
    camera_id: uuid.UUID | None = None
    evidence_reference: str | None = Field(None, max_length=500)
    metadata: dict[str, Any] | None = None


class EventResponse(BaseModel):
    """Event representation returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    event_type: EventType
    severity: EventSeverity
    status: EventStatus
    latitude: float | None = None
    longitude: float | None = None
    confidence: float
    first_detected_at: datetime
    last_detected_at: datetime
    verified_at: datetime | None
    resolved_at: datetime | None
    bus_id: uuid.UUID | None
    camera_id: uuid.UUID | None
    evidence_reference: str | None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")
    created_at: datetime
    updated_at: datetime


# ── GeoJSON Models ────────────────────────────────────────────────────────────


class GeoJSONGeometryPoint(BaseModel):
    """GeoJSON Point geometry: coordinates are [longitude, latitude]."""

    type: str = "Point"
    coordinates: list[float]  # [longitude, latitude]


class GeoJSONEventProperties(BaseModel):
    """Properties payload embedded inside an urban event GeoJSON Feature."""

    event_id: uuid.UUID
    event_type: EventType
    status: EventStatus
    severity: EventSeverity
    confidence: float
    detected_at: datetime


class GeoJSONEventFeature(BaseModel):
    """A single GeoJSON Feature representing an urban event."""

    type: str = "Feature"
    geometry: GeoJSONGeometryPoint | None = None
    properties: GeoJSONEventProperties


class GeoJSONFeatureCollection(BaseModel):
    """RFC 7946 GeoJSON FeatureCollection of urban events for GIS map dashboards."""

    type: str = "FeatureCollection"
    features: list[GeoJSONEventFeature] = Field(default_factory=list)

