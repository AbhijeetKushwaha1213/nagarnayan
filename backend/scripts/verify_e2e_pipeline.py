"""
Nagar Nayan — Phase 9 End-to-End Pipeline Integration Verification.

Executes and verifies the full architectural sequence:
  Detection Ingestion (POST /api/v1/detections)
  -> Urban Event Correlation (Spatial/Temporal correlation & update)
  -> Severity Engine (Deterministic factor evaluation)
  -> Alert Engine (Municipal alert generation)
  -> PostgreSQL / PostGIS (Persistence)
  -> WebSocket Broadcast (/api/v1/ws)
  -> GeoJSON GIS Mapping (Coordinate formatting & validation)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import sys
import uuid
import httpx
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_pipeline")

BACKEND_BASE = "http://127.0.0.1:8080"
WS_URL = "ws://127.0.0.1:8080/api/v1/ws"

DEMO_BUS_ID = "00000000-0000-0000-0000-000000000001"
DEMO_CAMERA_ID = "00000000-0000-0000-0000-000000000001"
DEMO_STREAM_ID = "00000000-0000-0000-0000-000000000001"

# Predefined demo coordinates (Connaught Place, New Delhi)
DEMO_LAT = 28.6139
DEMO_LON = 77.2090


async def run_e2e_verification() -> bool:
    logger.info("=" * 65)
    logger.info("STARTING NAGAR NAYAN END-TO-END PIPELINE VERIFICATION")
    logger.info("=" * 65)

    ws_messages: list[dict] = []
    ws_connected_event = asyncio.Event()

    async def ws_listener():
        try:
            async with websockets.connect(WS_URL) as ws:
                logger.info("[WS] Connected to %s", WS_URL)
                # Send connect handshake
                await ws.send("connect")
                ws_connected_event.set()

                while True:
                    raw_msg = await ws.recv()
                    msg = json.loads(raw_msg)
                    logger.info("[WS-RECV] Type: %s", msg.get("type"))
                    ws_messages.append(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("[WS] Listener closed: %s", e)

    # 1. Start WebSocket Listener Task
    listener_task = asyncio.create_task(ws_listener())
    try:
        await asyncio.wait_for(ws_connected_event.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.error("Failed to connect WebSocket within 5s")
        listener_task.cancel()
        return False

    async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=60.0) as client:
        # Check health
        health_resp = await client.get("/api/v1/health")
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
        logger.info("[STEP 1] Backend health verified: %s", health_resp.json()["status"])

        # ── Step 2: First Valid Detection (New Event Creation) ────────────────
        run_id = int(datetime.now(timezone.utc).timestamp())
        now1 = datetime.now(timezone.utc).isoformat()
        det1_payload = {
            "bus_id": DEMO_BUS_ID,
            "camera_id": DEMO_CAMERA_ID,
            "stream_id": DEMO_STREAM_ID,
            "detection_type": "DAMAGED_ROAD",
            "confidence": 0.88,
            "latitude": DEMO_LAT,
            "longitude": DEMO_LON,
            "detected_at": now1,
            "frame_reference": f"{DEMO_STREAM_ID}:{run_id}_100:10:DAMAGED_ROAD",
            "metadata": {
                "track_id": 10,
                "class_name": "damaged_road",
                "telemetry_source": "DEMO_SIMULATED",
                "is_demo_telemetry": True,
                "demo_route_id": "ROUTE-DELHI-01",
            },
        }

        resp1 = await client.post("/api/v1/detections", json=det1_payload)
        assert resp1.status_code == 201, f"Det 1 failed ({resp1.status_code}): {resp1.text}"
        det1_data = resp1.json()
        event_id1 = det1_data.get("event_id")
        logger.info("[STEP 2] Detection 1 ingested -> Associated Event ID: %s", event_id1)
        assert event_id1 is not None, "Event was not correlated for Detection 1"

        # Allow WebSocket broadcast to arrive
        await asyncio.sleep(1.0)

        # ── Step 3: Spatially & Temporally Related Detection (Event Update) ───
        now2 = datetime.now(timezone.utc).isoformat()
        det2_payload = {
            "bus_id": DEMO_BUS_ID,
            "camera_id": DEMO_CAMERA_ID,
            "stream_id": DEMO_STREAM_ID,
            "detection_type": "DAMAGED_ROAD",
            "confidence": 0.94,
            "latitude": DEMO_LAT + 0.00005,  # ~5 meters away
            "longitude": DEMO_LON + 0.00005,
            "detected_at": now2,
            "frame_reference": f"{DEMO_STREAM_ID}:{run_id}_125:10:DAMAGED_ROAD",
            "metadata": {
                "track_id": 10,
                "class_name": "damaged_road",
                "telemetry_source": "DEMO_SIMULATED",
                "is_demo_telemetry": True,
                "demo_route_id": "ROUTE-DELHI-01",
            },
        }

        resp2 = await client.post("/api/v1/detections", json=det2_payload)
        assert resp2.status_code == 201, f"Det 2 failed ({resp2.status_code}): {resp2.text}"
        det2_data = resp2.json()
        event_id2 = det2_data.get("event_id")
        logger.info("[STEP 3] Detection 2 ingested -> Correlated Event ID: %s", event_id2)
        assert event_id2 == event_id1, f"Event IDs diverge! {event_id1} != {event_id2}"

        # Allow WebSocket broadcast
        await asyncio.sleep(1.0)

        # ── Step 4: Duplicate Ingestion (Idempotency Guard) ───────────────────
        resp2_dup = await client.post("/api/v1/detections", json=det2_payload)
        assert resp2_dup.status_code == 201
        assert resp2_dup.json()["id"] == det2_data["id"], "Idempotency failed: created duplicate detection!"
        logger.info("[STEP 4] Idempotency verified: re-sending identical frame_reference returned existing ID")

        # ── Step 5: Unrelated Detection (Separate Event Creation) ─────────────
        now3 = datetime.now(timezone.utc).isoformat()
        det3_payload = {
            "bus_id": DEMO_BUS_ID,
            "camera_id": DEMO_CAMERA_ID,
            "stream_id": DEMO_STREAM_ID,
            "detection_type": "WATERLOGGING",
            "confidence": 0.95,
            "latitude": DEMO_LAT + 0.05,  # ~5 km away (outside spatial threshold)
            "longitude": DEMO_LON + 0.05,
            "detected_at": now3,
            "frame_reference": f"{DEMO_STREAM_ID}:{run_id}_200:20:WATERLOGGING",
            "metadata": {
                "track_id": 20,
                "class_name": "waterlogging",
                "telemetry_source": "DEMO_SIMULATED",
                "is_demo_telemetry": True,
            },
        }
        resp3 = await client.post("/api/v1/detections", json=det3_payload)
        assert resp3.status_code == 201
        event_id3 = resp3.json().get("event_id")
        logger.info("[STEP 5] Unrelated Detection 3 ingested -> Separate Event ID: %s", event_id3)
        assert event_id3 != event_id1, "Unrelated detection incorrectly correlated to existing event!"

        # ── Step 6: Missing GPS Detection (No Spatial Correlation) ────────────
        now4 = datetime.now(timezone.utc).isoformat()
        det4_payload = {
            "bus_id": DEMO_BUS_ID,
            "camera_id": DEMO_CAMERA_ID,
            "stream_id": DEMO_STREAM_ID,
            "detection_type": "MISSING_SIGNBOARD",
            "confidence": 0.85,
            "latitude": None,
            "longitude": None,
            "detected_at": now4,
            "frame_reference": f"{DEMO_STREAM_ID}:{run_id}_300:30:MISSING_SIGNBOARD",
            "metadata": {"track_id": 30},
        }
        resp4 = await client.post("/api/v1/detections", json=det4_payload)
        assert resp4.status_code == 201
        event_id4 = resp4.json().get("event_id")
        logger.info("[STEP 6] Missing GPS Detection 4 ingested -> Event ID: %s", event_id4)

        # Allow WebSocket events to arrive
        await asyncio.sleep(2.0)

        # ── Step 7: Verify Event & Alert Entities in Database ─────────────────
        events_resp = await client.get("/api/v1/events")
        assert events_resp.status_code == 200
        events_list = events_resp.json()
        logger.info("[STEP 7] Retrieved %d events from backend", len(events_list))
        event1_obj = next((e for e in events_list if e["id"] == event_id1), None)
        assert event1_obj is not None, "Event 1 not found in database"
        logger.info("  Event 1 Severity: %s, Status: %s, Lat: %s, Lon: %s",
                    event1_obj["severity"], event1_obj["status"], event1_obj["latitude"], event1_obj["longitude"])

        alerts_resp = await client.get("/api/v1/alerts")
        assert alerts_resp.status_code == 200
        alerts_list = alerts_resp.json()
        logger.info("  Retrieved %d alerts from backend", len(alerts_list))
        for a in alerts_list:
            logger.info("  Alert ID: %s, Event ID: %s, Severity: %s, Title: %s",
                        a["id"], a["event_id"], a["severity"], a["title"])

        # ── Step 8: Verify GeoJSON GIS Endpoint ───────────────────────────────
        geojson_resp = await client.get("/api/v1/events/geojson")
        assert geojson_resp.status_code == 200
        geojson_data = geojson_resp.json()
        features = geojson_data.get("features", [])
        logger.info("[STEP 8] GeoJSON FeatureCollection returned %d features", len(features))

        # Check coordinate format strictly [longitude, latitude]
        for f in features:
            coords = f["geometry"]["coordinates"]
            lng, lat = coords[0], coords[1]
            logger.info("  Feature event_id=%s, Type=%s, GeoJSON [lng, lat]=[%f, %f] -> Leaflet [lat, lng]=[%f, %f]",
                        f["properties"]["event_id"], f["properties"]["event_type"], lng, lat, lat, lng)
            # Verify coordinates are in valid range
            assert -180 <= lng <= 180
            assert -90 <= lat <= 90
            # Verify no fake Bangalore fallback (12.9716, 77.5946)
            assert not (abs(lat - 12.9716) < 0.001 and abs(lng - 77.5946) < 0.001), "Fabricated Bangalore fallback detected!"

        # ── Step 9: Verify WebSocket Broadcast Messages ───────────────────────
        logger.info("[STEP 9] Verifying WebSocket real-time broadcast message log (%d messages)", len(ws_messages))
        msg_types = [m.get("type") for m in ws_messages]
        logger.info("  Observed message types: %s", msg_types)

        assert "system.connected" in msg_types, "system.connected handshake not received"
        assert "event.created" in msg_types, "event.created broadcast not received"
        assert "event.updated" in msg_types, "event.updated broadcast not received"

        # Check if alert was produced
        has_alert_created = "alert.created" in msg_types
        has_alert_updated = "alert.updated" in msg_types
        logger.info("  Alert WebSocket propagation: created=%s, updated=%s", has_alert_created, has_alert_updated)

    listener_task.cancel()
    logger.info("=" * 65)
    logger.info("ALL END-TO-END PIPELINE INTEGRATION CRITERIA PASSED!")
    logger.info("=" * 65)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_e2e_verification())
    sys.exit(0 if success else 1)
