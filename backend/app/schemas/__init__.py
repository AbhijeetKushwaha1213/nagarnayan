"""Schemas package exports."""

from app.schemas.alert import AlertCreate, AlertResponse, AlertUpdate, EventSummary
from app.schemas.bus import BusCreate, BusResponse, BusUpdate
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate
from app.schemas.detection import DetectionCreate, DetectionResponse
from app.schemas.event import (
    EventCreate,
    EventResponse,
    EventUpdate,
    GeoJSONEventFeature,
    GeoJSONEventProperties,
    GeoJSONFeatureCollection,
    GeoJSONGeometryPoint,
)
from app.schemas.stream import StreamCreate, StreamResponse, StreamUpdate

__all__ = [
    "AlertCreate",
    "AlertUpdate",
    "AlertResponse",
    "EventSummary",
    "BusCreate",
    "BusUpdate",
    "BusResponse",
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "StreamCreate",
    "StreamUpdate",
    "StreamResponse",
    "DetectionCreate",
    "DetectionResponse",
    "EventCreate",
    "EventUpdate",
    "EventResponse",
    "GeoJSONGeometryPoint",
    "GeoJSONEventProperties",
    "GeoJSONEventFeature",
    "GeoJSONFeatureCollection",
]
