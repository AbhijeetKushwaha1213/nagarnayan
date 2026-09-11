"""
Stream Pydantic schemas — API request/response contracts.

Note: stream_url stores the RTSP endpoint as metadata.
The backend does NOT connect to or process this stream.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator

from app.models.stream import StreamProtocol, StreamStatus


class StreamCreate(BaseModel):
    """Payload for creating a new Stream."""

    camera_id: uuid.UUID
    stream_url: str = Field(
        ...,
        min_length=5,
        max_length=500,
        examples=["rtsp://localhost:8554/bus/KA-01-1234/front"],
        description="RTSP endpoint URL — stored as metadata only.",
    )
    protocol: StreamProtocol = StreamProtocol.rtsp
    status: StreamStatus = StreamStatus.inactive

    @field_validator("stream_url")
    @classmethod
    def validate_stream_url(cls, v: str) -> str:
        if not v.startswith(("rtsp://", "rtsps://", "rtmp://")):
            raise ValueError(
                "stream_url must start with rtsp://, rtsps://, or rtmp://"
            )
        return v


class StreamUpdate(BaseModel):
    """Payload for partially updating a Stream."""

    stream_url: str | None = Field(None, min_length=5, max_length=500)
    protocol: StreamProtocol | None = None
    status: StreamStatus | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None

    @field_validator("stream_url")
    @classmethod
    def validate_stream_url(cls, v: str | None) -> str | None:
        if v and not v.startswith(("rtsp://", "rtsps://", "rtmp://")):
            raise ValueError(
                "stream_url must start with rtsp://, rtsps://, or rtmp://"
            )
        return v


class StreamResponse(BaseModel):
    """Stream representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    camera_id: uuid.UUID
    stream_url: str
    protocol: StreamProtocol
    status: StreamStatus
    started_at: datetime | None
    stopped_at: datetime | None
    created_at: datetime
    updated_at: datetime
