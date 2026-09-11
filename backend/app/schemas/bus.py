"""Bus Pydantic schemas — API request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.bus import BusStatus


class BusCreate(BaseModel):
    """Payload for creating a new Bus."""

    bus_number: str = Field(..., min_length=1, max_length=50, examples=["KA-01-1234"])
    route_id: str | None = Field(None, max_length=100, examples=["ROUTE-7"])
    status: BusStatus = BusStatus.active


class BusUpdate(BaseModel):
    """Payload for partially updating a Bus (all fields optional)."""

    bus_number: str | None = Field(None, min_length=1, max_length=50)
    route_id: str | None = None
    status: BusStatus | None = None


class BusResponse(BaseModel):
    """Bus representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bus_number: str
    route_id: str | None
    status: BusStatus
    created_at: datetime
    updated_at: datetime
