# Videos

Drop prerecorded bus/road camera footage here. The streamer replays these files
as continuous simulated live camera feeds.

## Current file

| File                | Published as                       |
| ------------------- | ---------------------------------- |
| `bus_front_01.mp4`  | `rtsp://localhost:8554/bus/front`  |

`bus_front_01.mp4` ships as a short synthetic clip (1280×720, H.264, 25 fps) so
the pipeline is verifiable out of the box. **Replace it with real footage** —
keep the same filename and nothing else needs to change:

```bash
cp /path/to/your/dashcam.mp4 videos/bus_front_01.mp4
docker compose restart streamer
```

## Recommended source format

Any format FFmpeg can read works, but these settings stream most reliably:

- Container: `.mp4`
- Video codec: H.264 (`libx264`), `yuv420p` pixel format
- Resolution: 1280×720 or 1920×1080
- Frame rate: 25 or 30 fps
- Audio: not required (the streamer discards it with `-an`)

Convert anything else first:

```bash
ffmpeg -i input.mov -c:v libx264 -preset veryfast -pix_fmt yuv420p \
  -an -movflags +faststart videos/bus_front_01.mp4
```

## Using a different file or path

Set these in `.env` (see `.env.example`) — no code changes needed:

```bash
VIDEO_FILE=my_route_footage.mp4
STREAM_PATH=bus/NN-001/front
```

The file is mounted read-only at `/videos` inside the streamer container.

> Large media files are usually kept out of version control. Add
> `stream_server/videos/*.mp4` to `.gitignore` once you swap in real footage.
