"""
Dorothy OS v2.0 — WebSocket Connection Manager
Manages real-time bidirectional client connections with broadcast support.
Handles stale connections gracefully — no crashes on broadcast errors.
"""

import json
import logging
from typing import List, Dict, Any, Set
from fastapi import WebSocket

logger = logging.getLogger("Dorothy.WebSocket")


class ConnectionManager:
    """Manages WebSocket connections for real-time UI communication."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._closing: Set[int] = set()   # track sockets being cleaned up

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket client."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket client (safe to call multiple times)."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self._closing.discard(id(websocket))
            logger.info(f"Client disconnected. Active: {len(self.active_connections)}")

    async def send_personal(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """Send a JSON message to a specific client. Silently drops on error."""
        if id(websocket) in self._closing:
            return
        try:
            await websocket.send_json(message)
        except Exception:
            # Don't log noise — just clean up silently
            self._closing.add(id(websocket))
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a JSON message to all connected clients. Cleans up dead sockets."""
        if not self.active_connections:
            return
        dead = []
        for conn in list(self.active_connections):
            if id(conn) in self._closing:
                dead.append(conn)
                continue
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

    async def broadcast_except(self, message: Dict[str, Any], exclude: WebSocket) -> None:
        """Broadcast to all clients except one specific connection."""
        if not self.active_connections:
            return
        dead = []
        for conn in list(self.active_connections):
            if conn is exclude or id(conn) in self._closing:
                continue
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

    @property
    def client_count(self) -> int:
        """Number of currently connected clients."""
        return len(self.active_connections)


# Global singleton
manager = ConnectionManager()
