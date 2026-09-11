"""
WebSocket connection manager for Nagar Nayan backend.

Maintains in-memory active WebSocket connections, manages client lifecycle,
safely broadcasts JSON messages with bounded timeout, and provides error isolation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket client connections in process memory."""

    def __init__(self, send_timeout_seconds: float = 2.0) -> None:
        self._active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._send_timeout = send_timeout_seconds

    @property
    def active_count(self) -> int:
        """Return count of currently connected clients."""
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection and register client in active connections set."""
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info(
            "WebSocket client connected. Total active clients: %d",
            self.active_count,
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove client from active connections set cleanly."""
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info(
            "WebSocket client disconnected. Total active clients: %d",
            self.active_count,
        )

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast JSON message to all connected clients.

        Error Isolation & Backpressure:
          - Bounded send timeout (default 2.0s) prevents slow clients from stalling the backend.
          - Dead or disconnected sockets are safely collected and pruned.
          - Delivery failure for one client never interrupts broadcast to remaining clients.
        """
        if not isinstance(message, dict):
            logger.error("Cannot broadcast non-dict message: %r", message)
            return

        if not self._active_connections:
            logger.debug("No active WebSocket connections; broadcast skipped.")
            return

        try:
            async with self._lock:
                snapshot = list(self._active_connections)
        except Exception as exc:
            logger.error("Failed to acquire connection lock for broadcast: %s", exc)
            return

        dead_connections: list[WebSocket] = []

        for socket in snapshot:
            try:
                await asyncio.wait_for(
                    socket.send_json(message),
                    timeout=self._send_timeout,
                )
            except (WebSocketDisconnect, RuntimeError) as exc:
                logger.warning("Dead WebSocket client detected during broadcast: %s", exc)
                dead_connections.append(socket)
            except asyncio.TimeoutError:
                logger.warning(
                    "WebSocket broadcast to client timed out after %.1fs; dropping slow client.",
                    self._send_timeout,
                )
                dead_connections.append(socket)
            except Exception as exc:
                logger.error("Unexpected error delivering WebSocket message: %s", exc)
                dead_connections.append(socket)

        if dead_connections:
            try:
                async with self._lock:
                    for dead in dead_connections:
                        self._active_connections.discard(dead)
                logger.debug(
                    "Pruned %d dead WebSocket client(s). Remaining: %d",
                    len(dead_connections),
                    self.active_count,
                )
            except Exception as exc:
                logger.error("Failed to prune dead connections: %s", exc)

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Send JSON message directly to a specific connected client."""
        try:
            await asyncio.wait_for(
                websocket.send_json(message),
                timeout=self._send_timeout,
            )
        except Exception as exc:
            logger.warning("Failed to send personal WebSocket message: %s", exc)
            await self.disconnect(websocket)


# Global singleton instance
connection_manager = ConnectionManager()
