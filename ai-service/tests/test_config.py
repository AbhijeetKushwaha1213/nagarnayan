"""Unit tests for AI service configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import uuid
import pytest

from app.core.config import Settings, load_settings


def test_default_config() -> None:
    """Verify default configuration values."""
    cfg = Settings()
    assert cfg.RTSP_URL == "rtsp://localhost:8554/bus/front"
    assert cfg.FRAME_SAMPLE_FPS == 5.0
    assert cfg.RECONNECT_DELAY_SECONDS == 5.0
    assert cfg.MAX_RECONNECT_ATTEMPTS is None
    assert cfg.LOG_LEVEL == "INFO"
    assert cfg.STREAM_ID is None
    assert cfg.rtsp_stream_url == cfg.RTSP_URL

    # YOLO defaults
    assert cfg.YOLO_MODEL == "yolov8n.pt"
    assert cfg.YOLO_CONFIDENCE_THRESHOLD == 0.25
    assert cfg.YOLO_IOU_THRESHOLD == 0.45
    assert cfg.YOLO_DEVICE == "cpu"
    assert cfg.YOLO_IMAGE_SIZE == 640
    assert cfg.resolved_device == "cpu"

    # Phase 3 Tracking & Validation defaults
    assert cfg.TRACKING_ENABLED is True
    assert cfg.TRACKER_TYPE == "bytetrack.yaml"
    assert cfg.TRACKING_IOU_THRESHOLD == 0.50
    assert cfg.TRACK_MAX_AGE == 30
    assert cfg.VALIDATION_MIN_FRAMES == 3
    assert cfg.VALIDATION_WINDOW_FRAMES == 5
    assert cfg.VALIDATION_MIN_CONFIDENCE == 0.30


def test_custom_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that environment variables cleanly override defaults."""
    test_cam_id = str(uuid.uuid4())
    test_bus_id = str(uuid.uuid4())
    test_stream_id = str(uuid.uuid4())

    monkeypatch.setenv("RTSP_URL", "rtsp://custom-server:8554/live/stream")
    monkeypatch.setenv("FRAME_SAMPLE_FPS", "10.0")
    monkeypatch.setenv("RECONNECT_DELAY_SECONDS", "2.5")
    monkeypatch.setenv("MAX_RECONNECT_ATTEMPTS", "5")
    monkeypatch.setenv("CAMERA_ID", test_cam_id)
    monkeypatch.setenv("BUS_ID", test_bus_id)
    monkeypatch.setenv("STREAM_ID", test_stream_id)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("YOLO_MODEL", "models/custom_pothole.pt")
    monkeypatch.setenv("YOLO_CONFIDENCE_THRESHOLD", "0.60")
    monkeypatch.setenv("YOLO_IOU_THRESHOLD", "0.50")
    monkeypatch.setenv("YOLO_DEVICE", "cuda")
    monkeypatch.setenv("YOLO_IMAGE_SIZE", "1280")
    monkeypatch.setenv("TRACKING_ENABLED", "false")
    monkeypatch.setenv("TRACKER_TYPE", "custom_tracker.yaml")
    monkeypatch.setenv("TRACKING_IOU_THRESHOLD", "0.65")
    monkeypatch.setenv("TRACK_MAX_AGE", "15")
    monkeypatch.setenv("VALIDATION_MIN_FRAMES", "4")
    monkeypatch.setenv("VALIDATION_WINDOW_FRAMES", "8")
    monkeypatch.setenv("VALIDATION_MIN_CONFIDENCE", "0.45")

    cfg = Settings()
    assert cfg.RTSP_URL == "rtsp://custom-server:8554/live/stream"
    assert cfg.FRAME_SAMPLE_FPS == 10.0
    assert cfg.RECONNECT_DELAY_SECONDS == 2.5
    assert cfg.MAX_RECONNECT_ATTEMPTS == 5
    assert cfg.CAMERA_ID == test_cam_id
    assert cfg.BUS_ID == test_bus_id
    assert cfg.STREAM_ID == test_stream_id
    assert cfg.LOG_LEVEL == "DEBUG"
    assert cfg.YOLO_MODEL == "models/custom_pothole.pt"
    assert cfg.YOLO_CONFIDENCE_THRESHOLD == 0.60
    assert cfg.YOLO_IOU_THRESHOLD == 0.50
    assert cfg.YOLO_DEVICE == "cuda"
    assert cfg.YOLO_IMAGE_SIZE == 1280
    assert cfg.TRACKING_ENABLED is False
    assert cfg.TRACKER_TYPE == "custom_tracker.yaml"
    assert cfg.TRACKING_IOU_THRESHOLD == 0.65
    assert cfg.TRACK_MAX_AGE == 15
    assert cfg.VALIDATION_MIN_FRAMES == 4
    assert cfg.VALIDATION_WINDOW_FRAMES == 8
    assert cfg.VALIDATION_MIN_CONFIDENCE == 0.45


def test_validation_frames_invariant_enforced() -> None:
    """Verify VALIDATION_MIN_FRAMES cannot exceed VALIDATION_WINDOW_FRAMES."""
    with pytest.raises(ValueError, match="cannot exceed VALIDATION_WINDOW_FRAMES"):
        Settings(VALIDATION_MIN_FRAMES=6, VALIDATION_WINDOW_FRAMES=5)


def test_yolo_model_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify YOLO_MODEL_PATH alias works for backwards compatibility."""
    monkeypatch.delenv("YOLO_MODEL", raising=False)
    monkeypatch.setenv("YOLO_MODEL_PATH", "models/best_weights.pt")

    cfg = Settings()
    assert cfg.YOLO_MODEL == "models/best_weights.pt"
    assert cfg.yolo_model_path == "models/best_weights.pt"


def test_rtsp_stream_url_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify RTSP_STREAM_URL alias works for backwards compatibility."""
    monkeypatch.delenv("RTSP_URL", raising=False)
    monkeypatch.setenv("RTSP_STREAM_URL", "rtsp://alias-host:8554/test")

    cfg = Settings()
    assert cfg.RTSP_URL == "rtsp://alias-host:8554/test"


def test_invalid_sample_fps_rejected() -> None:
    """Verify non-positive sample FPS raises validation error."""
    with pytest.raises(Exception):
        Settings(FRAME_SAMPLE_FPS=0.0)

    with pytest.raises(Exception):
        Settings(FRAME_SAMPLE_FPS=-1.0)


def test_invalid_reconnect_delay_rejected() -> None:
    """Verify negative or too small reconnect delay raises validation error."""
    with pytest.raises(Exception):
        Settings(RECONNECT_DELAY_SECONDS=0.01)


def test_invalid_uuid_rejected() -> None:
    """Verify invalid UUID string raises validation error."""
    with pytest.raises(ValueError, match="Invalid UUID value"):
        Settings(CAMERA_ID="not-a-uuid-string")


def test_yaml_config_loading() -> None:
    """Verify loading settings from a YAML file."""
    yaml_content = """
rtsp_url: "rtsp://yaml-server:8554/bus/rear"
frame_sample_fps: 2.5
reconnect_delay_seconds: 3.0
max_reconnect_attempts: 8
log_level: "WARNING"
yolo_model: "yolov8s.pt"
yolo_confidence_threshold: 0.40
yolo_device: "cpu"
tracking_enabled: true
tracker_type: "bytetrack.yaml"
tracking_iou_threshold: 0.45
track_max_age: 20
validation_min_frames: 2
validation_window_frames: 4
validation_min_confidence: 0.35
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
        tf.write(yaml_content)
        tf_path = tf.name

    try:
        cfg = Settings.from_yaml(tf_path)
        assert cfg.RTSP_URL == "rtsp://yaml-server:8554/bus/rear"
        assert cfg.FRAME_SAMPLE_FPS == 2.5
        assert cfg.RECONNECT_DELAY_SECONDS == 3.0
        assert cfg.MAX_RECONNECT_ATTEMPTS == 8
        assert cfg.LOG_LEVEL == "WARNING"
        assert cfg.YOLO_MODEL == "yolov8s.pt"
        assert cfg.YOLO_CONFIDENCE_THRESHOLD == 0.40
        assert cfg.TRACKING_IOU_THRESHOLD == 0.45
        assert cfg.TRACK_MAX_AGE == 20
        assert cfg.VALIDATION_MIN_FRAMES == 2
        assert cfg.VALIDATION_WINDOW_FRAMES == 4
        assert cfg.VALIDATION_MIN_CONFIDENCE == 0.35

        loaded = load_settings(tf_path)
        assert loaded.RTSP_URL == "rtsp://yaml-server:8554/bus/rear"
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)
