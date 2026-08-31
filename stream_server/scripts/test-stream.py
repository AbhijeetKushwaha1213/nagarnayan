#!/usr/bin/env python3
"""
Nagar Nayan — OpenCV consumer test.

Verifies that external software can connect to the simulated live
camera feed and continuously receive frames:

    RTSP Stream  ->  OpenCV connects  ->  frames received

No AI processing here. This script only proves consumability.

Usage:
    python3 scripts/test-stream.py
    python3 scripts/test-stream.py rtsp://localhost:8554/bus/front
    python3 scripts/test-stream.py --frames 200 --show

Requires:
    pip install opencv-python
"""

from __future__ import annotations

import argparse
import os
import sys
import time

DEFAULT_URL = os.environ.get("STREAM_URL", "rtsp://localhost:8554/bus/front")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Consume the Nagar Nayan RTSP stream.")
    p.add_argument("url", nargs="?", default=DEFAULT_URL, help="RTSP URL to consume")
    p.add_argument(
        "--frames",
        type=int,
        default=100,
        help="stop after N frames (0 = run forever, Ctrl+C to stop)",
    )
    p.add_argument("--show", action="store_true", help="display frames in a window")
    p.add_argument(
        "--every", type=int, default=25, help="log every Nth frame (default: 25)"
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import cv2  # noqa: PLC0415
    except ImportError:
        print("ERROR: opencv-python is not installed.\n  pip install opencv-python")
        return 127

    # Prefer TCP for RTSP — far fewer torn/dropped frames than UDP.
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

    print("=" * 60)
    print(" Nagar Nayan — OpenCV stream consumer")
    print("=" * 60)
    print(f" Stream : {args.url}")
    print(f" Limit  : {args.frames or 'unlimited'} frames")
    print("=" * 60)

    print("Connecting...")
    cap = cv2.VideoCapture(args.url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print("FAILED to open stream.")
        print("  • Is the server up?        docker compose ps")
        print("  • Check streamer logs:     docker compose logs -f streamer")
        print("  • Verify with ffprobe:     ./scripts/verify-stream.sh")
        return 1

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    print(f"Connected. Reported geometry: {width}x{height} @ {src_fps:.1f} fps\n")

    received = 0
    failures = 0
    started = time.monotonic()

    try:
        while True:
            success, frame = cap.read()

            if not success:
                failures += 1
                print(f"Failed to receive frame (miss #{failures})")
                # Tolerate brief hiccups; bail out if the feed is truly gone.
                if failures >= 30:
                    print("Too many consecutive failures — stream appears down.")
                    break
                time.sleep(0.1)
                continue

            failures = 0
            received += 1

            if args.every > 0 and received % args.every == 0:
                elapsed = time.monotonic() - started
                fps = received / elapsed if elapsed > 0 else 0.0
                print(
                    f"Frame received: {frame.shape}  "
                    f"[#{received}  {fps:5.1f} fps  {elapsed:6.1f}s]"
                )

            if args.show:
                cv2.imshow("Nagar Nayan — bus/front", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    print("Window closed by user.")
                    break

            if args.frames and received >= args.frames:
                break
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()

    elapsed = time.monotonic() - started
    fps = received / elapsed if elapsed > 0 else 0.0

    print()
    print("=" * 60)
    print(f" Frames received : {received}")
    print(f" Duration        : {elapsed:.1f}s")
    print(f" Effective FPS   : {fps:.1f}")
    print("=" * 60)

    if received == 0:
        print(" RESULT: FAIL — connected but no frames arrived.")
        return 1

    # A real-time feed should pace near the source FPS, not blast frames.
    if src_fps and fps > src_fps * 3:
        print(" RESULT: PASS (frames received), but pacing looks fast-forwarded.")
        print("         Confirm ffmpeg is using '-re' in streamer/start-stream.sh.")
    else:
        print(" RESULT: PASS — stream behaves like a live camera feed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
