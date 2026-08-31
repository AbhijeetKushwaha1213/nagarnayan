#!/usr/bin/env bash
# ============================================================
# Nagar Nayan — RTSP stream verification
# Confirms the simulated live camera feed is up and delivering
# frames. Uses ffprobe (metadata) + ffmpeg (frame decode).
#
# Usage:
#   ./scripts/verify-stream.sh
#   ./scripts/verify-stream.sh rtsp://localhost:8554/bus/front
# ============================================================
set -uo pipefail

STREAM_URL="${1:-${STREAM_URL:-rtsp://localhost:8554/bus/front}}"
PROBE_SECONDS="${PROBE_SECONDS:-4}"

ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; }
info() { printf '  \033[36m•\033[0m %s\n' "$*"; }

echo
echo "============================================================"
echo " Nagar Nayan — stream verification"
echo "============================================================"
info "Target: ${STREAM_URL}"
echo

# ---- 0. Tooling ---------------------------------------------
for bin in ffprobe ffmpeg; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    bad "'$bin' not found. Install FFmpeg (brew install ffmpeg / apt install ffmpeg)."
    exit 127
  fi
done
ok "FFmpeg tooling present"

# ---- 1. Stream metadata -------------------------------------
echo
echo "[1/3] Reading stream metadata..."
META=$(ffprobe -v error -rtsp_transport tcp \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate \
  -of default=noprint_wrappers=1 \
  -timeout 5000000 \
  "${STREAM_URL}" 2>&1)

if [[ -z "${META}" ]]; then
  bad "No video stream found. Is the server running? (docker compose ps)"
  exit 1
fi
echo "${META}" | sed 's/^/      /'
ok "Stream is published and describable"

# ---- 2. Frame delivery --------------------------------------
echo
echo "[2/3] Decoding ~${PROBE_SECONDS}s of live frames..."
FRAME_LOG=$(ffmpeg -hide_banner -v error -stats \
  -rtsp_transport tcp -i "${STREAM_URL}" \
  -t "${PROBE_SECONDS}" -f null - 2>&1 | tail -n 1)

FRAMES=$(echo "${FRAME_LOG}" | grep -o 'frame= *[0-9]*' | grep -o '[0-9]*' | tail -n 1)
FRAMES="${FRAMES:-0}"

if (( FRAMES > 0 )); then
  ok "Received ${FRAMES} frames in ${PROBE_SECONDS}s (~$((FRAMES / PROBE_SECONDS)) fps)"
else
  bad "No frames decoded. Check: docker compose logs -f streamer"
  exit 1
fi

# ---- 3. Real-time pacing sanity -----------------------------
echo
echo "[3/3] Checking real-time pacing..."
FPS=$((FRAMES / PROBE_SECONDS))
if (( FPS >= 10 && FPS <= 60 )); then
  ok "Pacing looks like a live camera (~${FPS} fps, not fast-forwarded)"
else
  info "Observed ~${FPS} fps — verify TARGET_FPS / -re pacing if unexpected"
fi

echo
echo "============================================================"
echo " STREAM ACTIVE — ${STREAM_URL}"
echo "============================================================"
echo
echo "Watch it live:"
echo "  ffplay -rtsp_transport tcp ${STREAM_URL}"
echo "  vlc ${STREAM_URL}"
echo "  python3 scripts/test-stream.py"
echo
