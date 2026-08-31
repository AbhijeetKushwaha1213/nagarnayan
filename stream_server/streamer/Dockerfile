# ============================================================
# Nagar Nayan — FFmpeg streamer image
# Minimal Alpine + ffmpeg. `bash` is required for the
# /dev/tcp readiness probe used in start-stream.sh.
# ============================================================
FROM alpine:3.20

# ffmpeg (with libx264 + lavfi), bash for the startup script.
RUN apk add --no-cache ffmpeg bash \
    && ffmpeg -version | head -n 1

WORKDIR /app
COPY start-stream.sh /app/start-stream.sh
RUN chmod +x /app/start-stream.sh

ENTRYPOINT ["/app/start-stream.sh"]
