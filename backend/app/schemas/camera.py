"""Camera Pydantic schemas — API request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.camera import CameraStatus, CameraType


class CameraCreate(BaseModel):
    """Payload for creating a new Camera."""

    bus_id: uuid.UUID
    camera_type: CameraType = Field(..., examples=["front"])
    status: CameraStatus = CameraStatus.active


class CameraUpdate(BaseModel):
    """Payload for partially updating a Camera."""

    camera_type: CameraType | None = None
    status: CameraStatus | None = None


class CameraResponse(BaseModel):
    """Camera representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bus_id: uuid.UUID
    camera_type: CameraType
    status: CameraStatus
    created_at: datetime
    updated_at: datetime
