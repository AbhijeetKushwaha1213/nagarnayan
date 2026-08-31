#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8888}"
VIDEO_FILE="${VIDEO_FILE:-bus_front_01.mp4}"
STREAM_PATH="${STREAM_PATH:-bus/front}"
CLEAN_PATH="${STREAM_PATH#/}"

echo "============================================================"
echo "[STREAM-SERVER] Initializing Nagar Nayan Stream Server"
echo "============================================================"
echo "[STREAM-SERVER] HLS / HTTP Port: ${PORT}"
echo "[STREAM-SERVER] RTSP Port:       8554"
echo "[STREAM-SERVER] Video File:      ${VIDEO_FILE}"
echo "[STREAM-SERVER] Stream Path:     /${CLEAN_PATH}"
echo "============================================================"

# MediaMTX configuration overrides via environment variables
export MTX_HLSADDRESS=":${PORT}"
export MTX_RTSPADDRESS=":8554"

# Launch MediaMTX in background
mediamtx /app/mediamtx.yml &
MEDIAMTX_PID=$!

# Wait for MediaMTX RTSP listener
echo "[STREAM-SERVER] Waiting for MediaMTX to bind on port 8554..."
attempt=0
until (exec 3<>"/dev/tcp/127.0.0.1/8554") 2>/dev/null; do
  attempt=$((attempt + 1))
  sleep 1
  if [ $attempt -gt 15 ]; then
    echo "[STREAM-SERVER] MediaMTX taking longer to start, continuing..."
    break
  fi
done
exec 3>&- 2>/dev/null || true
echo "[STREAM-SERVER] MediaMTX is ready."

echo "[STREAM-SERVER] Starting continuous FFmpeg replay loop..."
echo "[STREAM-SERVER] Live HLS Stream: http://0.0.0.0:${PORT}/${CLEAN_PATH}/index.m3u8"

INPUT_PATH="/app/videos/${VIDEO_FILE}"
if [ ! -f "${INPUT_PATH}" ]; then
  echo "[STREAM-SERVER] WARNING: ${INPUT_PATH} not found. Using synthetic test pattern."
  INPUT_ARGS=(-re -f lavfi -i "testsrc2=size=1280x720:rate=25")
else
  INPUT_ARGS=(-re -stream_loop -1 -i "${INPUT_PATH}")
fi

while true; do
  ffmpeg -hide_banner -loglevel warning \
    "${INPUT_ARGS[@]}" \
    -an -c:v libx264 -preset veryfast -tune zerolatency -pix_fmt yuv420p \
    -r 25 -g 50 -b:v 2M -maxrate 2M -bufsize 4M \
    -f rtsp -rtsp_transport tcp "rtsp://127.0.0.1:8554/${CLEAN_PATH}" || true
  echo "[STREAM-SERVER] FFmpeg exited, restarting stream loop in 2s..."
  sleep 2
done
