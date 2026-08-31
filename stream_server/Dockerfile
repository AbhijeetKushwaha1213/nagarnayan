FROM bluenviron/mediamtx:1.9.3 AS mediamtx-bin

FROM alpine:3.20

RUN apk add --no-cache ffmpeg bash curl

# Copy MediaMTX binary from official image
COPY --from=mediamtx-bin /mediamtx /usr/local/bin/mediamtx

WORKDIR /app

COPY mediamtx/mediamtx.yml /app/mediamtx.yml
COPY videos /app/videos
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

EXPOSE 8554 8888 8889 10000

ENTRYPOINT ["/app/entrypoint.sh"]
