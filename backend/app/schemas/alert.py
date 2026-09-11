"""Alert Pydantic schemas — API request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.alert import AlertStatus, AlertType
from app.models.event import EventSeverity, EventStatus, EventType


class EventSummary(BaseModel):
    """Compact summary of the municipal Event linked to an Alert."""

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
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")


class AlertCreate(BaseModel):
    """Internal payload for synthesizing an actionable Alert from an Event."""

    event_id: uuid.UUID = Field(..., description="ID of the originating Event")
    alert_type: AlertType = Field(..., description="Categorization of the alert")
    severity: EventSeverity = Field(..., description="Severity level aligned with parent Event")
    status: AlertStatus = Field(AlertStatus.ACTIVE, description="Initial status")
    title: str = Field(..., max_length=255, description="Deterministic human-readable alert title")
    message: str = Field(..., max_length=2000, description="Deterministic human-readable alert description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")


class AlertManualCreate(BaseModel):
    """Payload for operator-created municipal alert via POST /api/v1/alerts."""

    event_id: uuid.UUID = Field(..., description="ID of the originating Event")
    title: str = Field(..., max_length=255, description="Alert title")
    message: str = Field(..., max_length=2000, description="Alert description")
    alert_type: AlertType | None = Field(None, description="Optional alert type (defaults to event mapping)")
    severity: EventSeverity | None = Field(None, description="Optional severity override (defaults to event severity)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata dictionary")


class AlertUpdate(BaseModel):
    """Payload for updating an existing Alert (lifecycle transition)."""

    status: AlertStatus | None = Field(None, description="New lifecycle status")
    metadata: dict[str, Any] | None = Field(None, description="Metadata updates to merge/replace")


class AlertResponse(BaseModel):
    """Alert representation returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    event_id: uuid.UUID
    alert_type: AlertType
    severity: EventSeverity
    status: AlertStatus
    title: str
    message: str
    triggered_at: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")
    event: EventSummary | None = None
    created_at: datetime
    updated_at: datetime
