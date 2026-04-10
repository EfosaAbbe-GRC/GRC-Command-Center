from fastapi import WebSocket
from typing import List, Dict
import json
from core.logger import logger

class ConnectionManager:
    """
    Manages active WebSocket connections for analyst terminals.
    Enforces real-time broadcast of GRC events.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket Synchronized", total_sessions=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket Terminated", total_sessions=len(self.active_connections))

    async def broadcast(self, message: Dict):
        """Broadcasts a JSON payload to all active analyst terminals."""
        payload = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                # Connection might be closed; disconnect logic handled by endpoint loop
                pass

manager = ConnectionManager()
