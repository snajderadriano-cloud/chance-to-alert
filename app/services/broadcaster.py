"""Broadcasting service for real-time WebSocket and push stream distribution."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Set

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class BroadcasterService:
    """Manages active WebSocket connections and broadcasts real-time threat updates."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Register an accepted WebSocket connection."""
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        self._connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send JSON message to all currently connected clients."""
        if not self._connections:
            return

        payload = json.dumps(message)
        dead_connections: List[WebSocket] = []

        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending message to WebSocket client: {e}")
                dead_connections.append(ws)

        for ws in dead_connections:
            self._connections.discard(ws)

    def active_connections_count(self) -> int:
        return len(self._connections)
