"""
WebSocket route for Nagar Nayan real-time dashboard updates.

Endpoint:
  WS /api/v1/ws
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import ConnectionManager, connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


def _get_manager() -> ConnectionManager:
    return connection_manager


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Real-time WebSocket endpoint for municipal dashboard clients.

    Lifecycle:
      1. Accepts connection and registers client in ConnectionManager.
      2. Listens for client messages / heartbeats (e.g. ping -> system.pong).
      3. Catches WebSocketDisconnect and cleans up registration.
    """
    manager = _get_manager()
    await manager.connect(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            # Lightweight client keepalive/heartbeat support
            stripped = text.strip().lower()
            if stripped in ("ping", '{"type":"ping"}', '{"type": "ping"}'):
                await websocket.send_json(
                    {
                        "type": "system.pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {"status": "alive"},
                    }
                )
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.debug("WebSocket client disconnected normally.")
    except Exception as exc:
        logger.warning("WebSocket client connection closed with error: %s", exc)
        await manager.disconnect(websocket)
