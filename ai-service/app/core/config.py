"""Configuration settings for the AI Video Intelligence Service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from typing_extensions import Self
import uuid

import yaml
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_uuid_str(val: Any) -> str:
    """Normalize UUID strings or integers into standard hyphenated UUID format."""
    if val is None:
        return ""
    if isinstance(val, uuid.UUID):
        return str(val)
    s = str(val).strip()
    if s.isdigit():
        return str(uuid.UUID(int=int(s)))
    try:
        return str(uuid.UUID(s))
    except ValueError as exc:
        raise ValueError(f"Invalid UUID value {val!r}: must be integer or UUID string") from exc


class Settings(BaseSettings):
    """Configuration settings for the AI Video Intelligence Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── RTSP Stream Ingestion ──────────────────────────────────────────────────
    RTSP_URL: str = Field(
        default="rtsp://localhost:8554/bus/front",
        validation_alias=AliasChoices("RTSP_URL", "RTSP_STREAM_URL"),
        description="RTSP video source URL from MediaMTX or stream server",
    )
    FRAME_SAMPLE_FPS: float = Field(
        default=5.0,
        gt=0.0,
        le=60.0,
        description="Target sampling rate (frames processed per second)",
    )
    RECONNECT_DELAY_SECONDS: float = Field(
        default=5.0,
        ge=0.1,
        le=60.0,
        description="Seconds to wait before reconnecting after stream loss",
    )
    MAX_RECONNECT_ATTEMPTS: int | None = Field(
        default=None,
        ge=0,
        description="Maximum consecutive reconnection attempts (0 or None for unlimited)",
    )
    STREAM_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        ge=1.0,
        le=120.0,
        description="Maximum seconds without a frame before declaring stream stalled",
    )
    STATUS_LOG_INTERVAL_SECONDS: float = Field(
        default=5.0,
        ge=0.5,
        le=300.0,
        description="Interval in seconds for periodic throughput diagnostics logging",
    )

    # ── Source Identity ────────────────────────────────────────────────────────
    BUS_ID: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        description="UUID of the bus carrying this camera",
    )
    CAMERA_ID: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        description="UUID of this camera",
    )
    STREAM_ID: str | None = Field(
        default=None,
        description="Optional UUID of the stream registered in backend",
    )

    @field_validator("BUS_ID", "CAMERA_ID", mode="before")
    @classmethod
    def validate_and_normalize_uuid(cls, value: Any) -> str:
        return _normalize_uuid_str(value)

    @field_validator("STREAM_ID", mode="before")
    @classmethod
    def validate_optional_uuid(cls, value: Any) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _normalize_uuid_str(value)

    # ── YOLO Object Detection (Phase 2) ────────────────────────────────────────
    YOLO_MODEL: str = Field(
        default="yolov8n.pt",
        validation_alias=AliasChoices("YOLO_MODEL", "YOLO_MODEL_PATH"),
        description="YOLO model path or name (e.g. yolov8n.pt or models/best.pt)",
    )
    YOLO_CONFIDENCE_THRESHOLD: float = Field(
        default=0.25,
        gt=0.0,
        lt=1.0,
        description="Minimum confidence score threshold (0.0 < conf < 1.0)",
    )
    YOLO_IOU_THRESHOLD: float = Field(
        default=0.45,
        gt=0.0,
        lt=1.0,
        description="Non-Maximum Suppression (NMS) IoU threshold (0.0 < iou < 1.0)",
    )
    YOLO_DEVICE: str = Field(
        default="cpu",
        description="Target inference hardware: cpu, cuda, mps, auto",
    )
    YOLO_IMAGE_SIZE: int = Field(
        default=640,
        gt=32,
        description="Inference input image resolution (square)",
    )

    @property
    def resolved_device(self) -> str:
        """Resolve "auto" to "cuda", "mps", or "cpu" dynamically based on host availability."""
        dev = self.YOLO_DEVICE.strip().lower()
        if dev == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return "mps"
            except Exception:
                pass
            return "cpu"
        return dev

    # ── Object Tracking & Validation (Phase 3) ──────────────────────────────────
    TRACKING_ENABLED: bool = Field(
        default=True,
        description="Whether object tracking is enabled",
    )
    TRACKER_TYPE: str = Field(
        default="bytetrack.yaml",
        description="Ultralytics tracker configuration file (e.g. bytetrack.yaml)",
    )
    TRACKING_IOU_THRESHOLD: float = Field(
        default=0.50,
        gt=0.0,
        le=1.0,
        description="Spatial IoU threshold for matching unassigned detections across frames",
    )
    TRACK_MAX_AGE: int = Field(
        default=30,
        ge=1,
        description="Maximum consecutive unobserved frames before an inactive track is expired",
    )
    VALIDATION_MIN_FRAMES: int = Field(
        default=3,
        ge=1,
        description="Minimum observations required within sliding window to validate track",
    )
    VALIDATION_WINDOW_FRAMES: int = Field(
        default=5,
        ge=1,
        description="Sliding window size in frames for multi-frame observation validation",
    )
    VALIDATION_MIN_CONFIDENCE: float = Field(
        default=0.30,
        gt=0.0,
        lt=1.0,
        description="Minimum average confidence required over window to validate track",
    )

    # ── Backend Client Integration (Phase 4) ──────────────────────────────────
    BACKEND_BASE_URL: str = Field(
        default="http://localhost:8080",
        validation_alias=AliasChoices("BACKEND_BASE_URL", "BACKEND_URL", "BACKEND_API_URL"),
        description="FastAPI Backend root URL",
    )
    BACKEND_API_PREFIX: str = Field(
        default="/api/v1",
        description="Backend API URL path prefix",
    )
    BACKEND_REQUEST_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        gt=0.0,
        description="HTTP request timeout to backend",
    )
    BACKEND_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        description="Max HTTP retry attempts",
    )
    BACKEND_RETRY_DELAY_SECONDS: float = Field(
        default=1.0,
        gt=0.0,
        description="HTTP retry initial delay seconds",
    )
    BACKEND_RETRY_BACKOFF_BASE: float = Field(
        default=0.5,
        gt=0.0,
        description="Exponential backoff base in seconds",
    )
    BACKEND_QUEUE_MAX_SIZE: int = Field(
        default=100,
        ge=1,
        description="Maximum bounded queue size for detection sender",
    )
    BACKEND_DUPLICATE_COOLDOWN_SECONDS: float = Field(
        default=10.0,
        ge=0.0,
        description="Duplicate detection cooldown window",
    )

    DETECTION_SEND_COOLDOWN_SECONDS: float = Field(
        default=10.0,
        ge=0.0,
        description="Duplicate detection send cooldown window in seconds",
    )
    CAMERA_LATITUDE: float = Field(
        default=28.6139,
        description="Camera nominal latitude for geo-tagging",
    )
    CAMERA_LONGITUDE: float = Field(
        default=77.2090,
        description="Camera nominal longitude for geo-tagging",
    )

    # ── Phase 9: Controlled Demo Telemetry Configuration ─────────────────────
    DEMO_TELEMETRY_ENABLED: bool = Field(
        default=False,
        description="Explicitly enable simulated GPS coordinates for demo video streams with no onboard GPS",
    )
    DEMO_TELEMETRY_LATITUDE: float = Field(
        default=28.6139,
        description="Predefined demo simulated GPS latitude (e.g. Connaught Place, New Delhi)",
    )
    DEMO_TELEMETRY_LONGITUDE: float = Field(
        default=77.2090,
        description="Predefined demo simulated GPS longitude (e.g. Connaught Place, New Delhi)",
    )
    DEMO_TELEMETRY_ROUTE_ID: str = Field(
        default="ROUTE-DELHI-01",
        description="Predefined demo route identifier for simulated telemetry",
    )

    FRAME_REFERENCE_PREFIX: str = Field(
        default="http://localhost:9000/frames",
        description="Frame reference URL prefix",
    )

    BACKEND_API_PREFIX: str = Field(
        default="/api/v1",
        description="Backend API URL path prefix",
    )

    @model_validator(mode="after")
    def validate_tracking_and_validation_settings(self) -> Self:
        if self.VALIDATION_MIN_FRAMES > self.VALIDATION_WINDOW_FRAMES:
            raise ValueError(
                f"VALIDATION_MIN_FRAMES ({self.VALIDATION_MIN_FRAMES}) cannot exceed "
                f"VALIDATION_WINDOW_FRAMES ({self.VALIDATION_WINDOW_FRAMES})"
            )
        return self

    # ── Application Metadata & Logging ─────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    SERVICE_NAME: str = Field(
        default="Nagar Nayan AI Service",
        description="Human-readable service identifier",
    )
    SERVICE_VERSION: str = Field(
        default="3.0.0",
        description="Semantic service version",
    )

    @property

    @property
    def BACKEND_URL(self) -> str:
        """Alias for BACKEND_BASE_URL."""
        return self.BACKEND_BASE_URL

    @property
    @property
    def BACKEND_API_URL(self) -> str:
        """Alias for BACKEND_BASE_URL."""
        return self.BACKEND_BASE_URL

    @property
    def rtsp_stream_url(self) -> str:
        """Backwards-compatible alias for RTSP_URL."""
        return self.RTSP_URL

    @property
    def yolo_model_path(self) -> str:
        """Backwards-compatible alias for YOLO_MODEL."""
        return self.YOLO_MODEL

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> Settings:
        """Load settings from a YAML configuration file, overlaid on defaults."""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Convert keys to uppercase to match settings fields
        upper_data = {k.upper(): v for k, v in data.items()}
        return cls(**upper_data)


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load settings from config file if provided, otherwise from environment."""
    if config_path and Path(config_path).exists():
        return Settings.from_yaml(config_path)
    return Settings()


settings = load_settings()
