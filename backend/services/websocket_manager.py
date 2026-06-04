import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("JARVIS.WebSocketManager")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to specific client: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        
        logger.debug(f"Broadcasting message of type: {message.get('type')}")
        disconnected_sockets = []
        
        # Capture connections snapshot to prevent mutation during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected_sockets.append(connection)
                
        for socket in disconnected_sockets:
            self.disconnect(socket)

# Global singleton connection manager
manager = ConnectionManager()
