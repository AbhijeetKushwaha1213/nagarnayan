#!/usr/bin/env bash
# ============================================================
# Nagar Nayan — Local Stream Server Runner (macOS / Linux)
# Runs MediaMTX and FFmpeg streamer directly without Docker.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

log() { echo "[LOCAL-STREAM] $*"; }

# 1. Verify ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  log "ERROR: ffmpeg is not installed. Run: brew install ffmpeg"
  exit 1
fi

# 2. Verify or install mediamtx
if ! command -v mediamtx >/dev/null 2>&1; then
  log "mediamtx not found. Installing via Homebrew..."
  if command -v brew >/dev/null 2>&1; then
    brew install mediamtx
  else
    log "ERROR: Homebrew not found. Please install mediamtx or Docker."
    exit 1
  fi
fi

# Trap to kill background processes on exit
cleanup() {
  log "Stopping stream server..."
  kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "============================================================"
log "Starting MediaMTX server..."
log "============================================================"
mediamtx mediamtx/mediamtx.yml &
MEDIAMTX_PID=$!

# Wait for RTSP port 8554
log "Waiting for MediaMTX on port 8554..."
until (exec 3<>"/dev/tcp/127.0.0.1/8554") 2>/dev/null; do
  sleep 1
done
exec 3>&- 2>/dev/null || true
log "MediaMTX is ready."

log "============================================================"
log "Starting FFmpeg stream: videos/bus_front_01.mp4"
log "Publishing to: rtsp://localhost:8554/bus/front"
log "============================================================"

while true; do
  ffmpeg -hide_banner -loglevel warning \
    -re -stream_loop -1 -i "videos/bus_front_01.mp4" \
    -an -c:v libx264 -preset veryfast -tune zerolatency -pix_fmt yuv420p \
    -r 25 -g 50 -b:v 2M -maxrate 2M -bufsize 4M \
    -f rtsp -rtsp_transport tcp "rtsp://localhost:8554/bus/front" || true
  log "FFmpeg exited, restarting stream in 2s..."
  sleep 2
done
