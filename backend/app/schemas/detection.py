"""Detection Pydantic schemas — API request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class DetectionCreate(BaseModel):
    """Payload for registering a raw AI detection."""

    camera_id: uuid.UUID = Field(..., description="ID of the observing Camera")
    bus_id: uuid.UUID = Field(..., description="ID of the Bus carrying the camera")
    stream_id: uuid.UUID | None = Field(None, description="Optional ID of the Stream")
    detection_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of detected issue (e.g. POTHOLE, DAMAGED_ROAD)",
        examples=["POTHOLE"],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
        examples=[0.91],
    )
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
    detected_at: datetime = Field(
        ...,
        description="Time the detection was made (timezone-aware ISO 8601)",
    )
    frame_reference: str | None = Field(
        None,
        max_length=500,
        description="Reference to frame, image snapshot, or video timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary AI-specific metadata (e.g. bounding boxes)",
    )
    event_id: uuid.UUID | None = Field(
        None,
        description="Optional link to a validated Event",
    )


class DetectionResponse(BaseModel):
    """Detection representation returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    camera_id: uuid.UUID
    bus_id: uuid.UUID
    stream_id: uuid.UUID | None = None
    detection_type: str
    confidence: float
    latitude: float | None = None
    longitude: float | None = None
    detected_at: datetime
    frame_reference: str | None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")
    event_id: uuid.UUID | None
    created_at: datetime

    @computed_field
    @property
    def detection_id(self) -> uuid.UUID:
        """Alias for id providing client contract compatibility."""
        return self.id
