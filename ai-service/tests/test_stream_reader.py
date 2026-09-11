"""Tests for StreamReader with mocked OpenCV VideoCapture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.stream.reader import StreamReader


class TestStreamReader:

    def test_initial_state_not_connected(self) -> None:
        reader = StreamReader(rtsp_url="rtsp://localhost:8554/bus/front")
        assert not reader.is_connected
        assert reader.stream_width == 0
        assert reader.stream_height == 0
        assert reader.stream_fps == 0.0

    @patch("cv2.VideoCapture")
    def test_connect_success(self, mock_cv_capture: MagicMock) -> None:
        instance = MagicMock()
        instance.isOpened.return_value = True
        instance.get.side_effect = lambda prop: {3: 1920, 4: 1080, 5: 25.0}.get(prop, 0)
        mock_cv_capture.return_value = instance

        reader = StreamReader(rtsp_url="rtsp://localhost:8554/bus/front")
        success = reader.connect()

        assert success is True
        assert reader.is_connected is True
        assert reader.stream_width == 1920
        assert reader.stream_height == 1080
        assert reader.stream_fps == 25.0

    @patch("cv2.VideoCapture")
    def test_connect_failure(self, mock_cv_capture: MagicMock) -> None:
        instance = MagicMock()
        instance.isOpened.return_value = False
        mock_cv_capture.return_value = instance

        reader = StreamReader(rtsp_url="rtsp://invalid-host:8554/stream")
        success = reader.connect()

        assert success is False
        assert reader.is_connected is False
        instance.release.assert_called_once()

    @patch("cv2.VideoCapture")
    def test_read_frame_success(self, mock_cv_capture: MagicMock) -> None:
        fake_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        instance = MagicMock()
        instance.isOpened.return_value = True
        instance.read.return_value = (True, fake_frame)
        mock_cv_capture.return_value = instance

        reader = StreamReader(rtsp_url="rtsp://localhost:8554/bus/front")
        reader.connect()

        ret, frame, timestamp = reader.read_frame()
        assert ret is True
        assert frame is not None
        assert frame.shape == (720, 1280, 3)
        assert timestamp > 0

    @patch("cv2.VideoCapture")
    def test_read_frame_failure_triggers_disconnect(self, mock_cv_capture: MagicMock) -> None:
        instance = MagicMock()
        instance.isOpened.return_value = True
        instance.read.return_value = (False, None)  # Stream drops
        mock_cv_capture.return_value = instance

        reader = StreamReader(rtsp_url="rtsp://localhost:8554/bus/front")
        reader.connect()
        assert reader.is_connected is True

        ret, frame, _ = reader.read_frame()
        assert ret is False
        assert frame is None
        assert reader.is_connected is False
        instance.release.assert_called()

    @patch("cv2.VideoCapture")
    def test_close_releases_resources(self, mock_cv_capture: MagicMock) -> None:
        instance = MagicMock()
        instance.isOpened.return_value = True
        mock_cv_capture.return_value = instance

        reader = StreamReader(rtsp_url="rtsp://localhost:8554/bus/front")
        reader.connect()
        reader.close()

        assert reader.is_connected is False
        instance.release.assert_called()
