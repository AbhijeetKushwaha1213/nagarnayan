"""Streams package alias for backwards compatibility."""

from app.streams.rtsp_reader import RTSPReader, StreamReader
from app.streams.stream_manager import StreamManager

__all__ = ["RTSPReader", "StreamReader", "StreamManager"]
