# FFmpeg Streamer

The **Streamer** container simulates an IP camera by reading recorded video files from `/videos` and publishing them as live RTSP streams to MediaMTX.

## Responsibilities

1. **Real-time playback (`-re`)**: Paces frames at real-time speeds to emulate a physical camera rather than dumping frames as fast as possible.
2. **Continuous looping (`-stream_loop -1` + bash safety loop)**: Automatically restarts playback immediately when the video ends without dropping the RTSP feed.
3. **Resilient startup & retries**: Polls for MediaMTX availability before attempting to stream; automatically reconnects if the media server restarts.
4. **Synthetic fallback**: If the requested video is not yet present, streams a 720p test pattern (`testsrc2`) so the downstream pipeline can still be tested.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MEDIAMTX_HOST` | `mediamtx` | Hostname of MediaMTX container |
| `MEDIAMTX_RTSP_PORT` | `8554` | RTSP port on MediaMTX |
| `RTSP_TRANSPORT` | `tcp` | RTSP transport protocol (`tcp` or `udp`) |
| `VIDEO_FILE` | `bus_front_01.mp4` | Name of MP4 file inside `./videos/` |
| `STREAM_PATH` | `bus/front` | RTSP mount point (e.g. `/bus/front`) |
| `STREAM_COPY` | `false` | When `true`, passes H.264 stream directly without re-encoding (lower CPU) |
| `TARGET_FPS` | `25` | Target frames per second |
| `GOP` | `50` | Keyframe interval (Group of Pictures) |
| `RETRY_DELAY` | `3` | Seconds to wait before reconnecting on failure |
