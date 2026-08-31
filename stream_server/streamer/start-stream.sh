#!/usr/bin/env bash
# ============================================================
# Nagar Nayan — FFmpeg live-camera simulator
# Reads a recorded MP4 and publishes it to MediaMTX over RTSP,
# in real time, looping forever, with retry/restart logic.
# ============================================================
set -uo pipefail

# ---- Configuration (all overridable via environment) --------
VIDEO_DIR="${VIDEO_DIR:-/videos}"
VIDEO_FILE="${VIDEO_FILE:-bus_front_01.mp4}"
STREAM_PATH="${STREAM_PATH:-bus/front}"
MEDIAMTX_HOST="${MEDIAMTX_HOST:-mediamtx}"
MEDIAMTX_RTSP_PORT="${MEDIAMTX_RTSP_PORT:-8554}"
RTSP_TRANSPORT="${RTSP_TRANSPORT:-tcp}"
STREAM_COPY="${STREAM_COPY:-false}"
TARGET_FPS="${TARGET_FPS:-25}"
GOP="${GOP:-50}"
RETRY_DELAY="${RETRY_DELAY:-3}"

INPUT_PATH="${VIDEO_DIR}/${VIDEO_FILE}"
# Strip any leading slash from STREAM_PATH to avoid a double slash.
CLEAN_PATH="${STREAM_PATH#/}"
PUBLISH_URL="rtsp://${MEDIAMTX_HOST}:${MEDIAMTX_RTSP_PORT}/${CLEAN_PATH}"

log() { echo "[STREAMER] $*"; }
rule() { log "------------------------------------------------------------"; }

rule
log "Starting video stream"
rule
log "Input:       ${VIDEO_FILE} (${INPUT_PATH})"
log "Stream path: /${CLEAN_PATH}"
log "Publish URL: ${PUBLISH_URL}"
log "Transport:   ${RTSP_TRANSPORT}   Copy: ${STREAM_COPY}   FPS: ${TARGET_FPS}"
rule

# ---- Wait for MediaMTX to accept RTSP connections -----------
log "Connecting to MediaMTX..."
attempt=0
until (exec 3<>"/dev/tcp/${MEDIAMTX_HOST}/${MEDIAMTX_RTSP_PORT}") 2>/dev/null; do
  attempt=$((attempt + 1))
  log "MediaMTX not ready yet (attempt ${attempt}); retrying in ${RETRY_DELAY}s..."
  sleep "${RETRY_DELAY}"
done
exec 3>&- 2>/dev/null || true
log "MediaMTX is reachable."

# ---- Resolve the input source -------------------------------
# If the recording is missing we fall back to a synthetic test
# pattern so the pipeline is still verifiable end to end.
declare -a INPUT_ARGS
FORCE_ENCODE="false"
if [[ -f "${INPUT_PATH}" ]]; then
  INPUT_ARGS=(-re -stream_loop -1 -i "${INPUT_PATH}")
  SOURCE_DESC="file ${VIDEO_FILE} (looping)"
else
  log "WARNING: '${INPUT_PATH}' not found."
  log "         Drop your recording at videos/${VIDEO_FILE} and restart."
  log "         Falling back to a synthetic test pattern for now."
  INPUT_ARGS=(-re -f lavfi -i "testsrc2=size=1280x720:rate=${TARGET_FPS}")
  SOURCE_DESC="synthetic test pattern"
  FORCE_ENCODE="true"   # a raw lavfi source cannot be stream-copied
fi

# ---- Encoding args ------------------------------------------
declare -a ENCODE_ARGS
if [[ "${STREAM_COPY}" == "true" && "${FORCE_ENCODE}" == "false" ]]; then
  # Faithful, low-CPU passthrough (requires an H.264 source).
  ENCODE_ARGS=(-an -c:v copy)
else
  # Re-encode to H.264 for maximum RTSP / OpenCV / VLC compatibility.
  ENCODE_ARGS=(
    -an
    -c:v libx264 -preset veryfast -tune zerolatency
    -pix_fmt yuv420p
    -r "${TARGET_FPS}" -g "${GOP}" -sc_threshold 0
    -b:v 2M -maxrate 2M -bufsize 4M
  )
fi

declare -a OUTPUT_ARGS=(-f rtsp -rtsp_transport "${RTSP_TRANSPORT}" "${PUBLISH_URL}")

# ---- Publish loop (safety net around ffmpeg) ----------------
# `-stream_loop -1` already loops the file forever; this outer
# loop only restarts ffmpeg if it exits for any other reason.
while true; do
  log "Publishing live stream — source: ${SOURCE_DESC}"
  log "Stream active → ${PUBLISH_URL}"
  ffmpeg -hide_banner -loglevel warning -fflags +genpts \
    "${INPUT_ARGS[@]}" "${ENCODE_ARGS[@]}" "${OUTPUT_ARGS[@]}"
  code=$?
  log "ffmpeg exited (code ${code}) — restarting in ${RETRY_DELAY}s..."
  sleep "${RETRY_DELAY}"
done
