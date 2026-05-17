import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.setdefault(client_id, []).append(websocket)
        logger.debug("WS connected: client=%s total=%d", client_id, len(self.active[client_id]))

    def disconnect(self, client_id: str, websocket: WebSocket) -> None:
        connections = self.active.get(client_id, [])
        if websocket in connections:
            connections.remove(websocket)

    async def broadcast_to_client(self, client_id: str, message: dict) -> None:
        dead: List[WebSocket] = []
        for ws in list(self.active.get(client_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(client_id, ws)


manager = ConnectionManager()
