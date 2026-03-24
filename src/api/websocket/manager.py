"""
WebSocket connection manager for real-time job updates.
"""
from fastapi import WebSocket
from typing import Dict, List, Set
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections organized by channels (job IDs)."""
    
    def __init__(self):
        # channel_name -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Accept and register a WebSocket connection to a channel."""
        await websocket.accept()
        
        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)
        
        logger.info(f"WebSocket connected to channel: {channel}")
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove a WebSocket connection from a channel."""
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]
        
        logger.info(f"WebSocket disconnected from channel: {channel}")
    
    async def broadcast(self, channel: str, message: dict):
        """Broadcast a message to all connections in a channel."""
        if channel not in self.active_connections:
            return
        
        json_message = json.dumps(message)
        dead_connections = []
        
        for websocket in self.active_connections[channel]:
            try:
                await websocket.send_text(json_message)
            except Exception as e:
                logger.warning(f"Failed to send message: {e}")
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws, channel)
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")


# Singleton manager
manager = ConnectionManager()


async def broadcast_job_event(job_id: int, event_type: str, data: dict):
    """Broadcast an event for a specific job."""
    channel = f"job_{job_id}"
    message = {
        "event": event_type,
        "job_id": job_id,
        "data": data
    }
    await manager.broadcast(channel, message)
