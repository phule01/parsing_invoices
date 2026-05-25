from fastapi import WebSocket
from typing import List, Dict, Set, Any
import asyncio
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects (like datetime) to JSON-compatible types.
    This ensures datetime objects and other objects can be sent over WebSocket.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Maps user_id to set of active WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Broadcast connections (not tied to specific user)
        self.broadcast_connections: Set[WebSocket] = set()
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Register a new WebSocket connection."""
        await websocket.accept()
        async with self.lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
            logger.info(f"WebSocket connected for user {user_id}")
    
    async def disconnect(self, user_id: int, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self.lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def broadcast_to_user(self, user_id: int, message: dict):
        """Send message to all connections of a specific user."""
        message["timestamp"] = datetime.utcnow().isoformat()
        # Ensure all data is JSON-serializable
        message = serialize_for_json(message)
        async with self.lock:
            if user_id in self.active_connections:
                disconnected = set()
                for connection in self.active_connections[user_id]:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error(f"Error sending message to user {user_id}: {e}")
                        disconnected.add(connection)
                # Clean up disconnected connections
                self.active_connections[user_id] -= disconnected
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected users."""
        message["timestamp"] = datetime.utcnow().isoformat()
        # Ensure all data is JSON-serializable
        message = serialize_for_json(message)
        async with self.lock:
            disconnected_users = []
            for user_id, connections in self.active_connections.items():
                disconnected = set()
                for connection in connections:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to user {user_id}: {e}")
                        disconnected.add(connection)
                if disconnected:
                    self.active_connections[user_id] -= disconnected
                if not self.active_connections[user_id]:
                    disconnected_users.append(user_id)
            
            # Clean up empty user connections
            for user_id in disconnected_users:
                del self.active_connections[user_id]
    
    async def notify_invoice_created(self, invoice_id: int, invoice_data: dict, user_id: int, source: str = "api"):
        """Notify all users about a new invoice."""
        message = {
            "type": "invoice_created",
            "entity_type": "invoice",
            "entity_id": invoice_id,
            "data": invoice_data,
            "user_id": user_id,
            "source": source
        }
        await self.broadcast_to_all(message)
    
    async def notify_invoice_updated(self, invoice_id: int, changes: dict, user_id: int, source: str = "api"):
        """Notify all users about an invoice update."""
        message = {
            "type": "invoice_updated",
            "entity_type": "invoice",
            "entity_id": invoice_id,
            "changes": changes,
            "user_id": user_id,
            "source": source
        }
        await self.broadcast_to_all(message)
    
    async def notify_product_created(self, product_id: int, product_data: dict, user_id: int, source: str = "api"):
        """Notify all users about a new product."""
        message = {
            "type": "product_created",
            "entity_type": "product",
            "entity_id": product_id,
            "data": product_data,
            "user_id": user_id,
            "source": source
        }
        await self.broadcast_to_all(message)
    
    async def notify_product_updated(self, product_id: int, changes: dict, user_id: int, source: str = "api"):
        """Notify all users about a product update."""
        message = {
            "type": "product_updated",
            "entity_type": "product",
            "entity_id": product_id,
            "changes": changes,
            "user_id": user_id,
            "source": source
        }
        await self.broadcast_to_all(message)
    
    async def notify_telegram_update(self, entity_type: str, entity_id: int, data: dict):
        """Notify users about data from Telegram."""
        message = {
            "type": f"{entity_type}_created_from_telegram",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "data": data,
            "source": "telegram"
        }
        await self.broadcast_to_all(message)
    
    def get_active_user_count(self) -> int:
        """Get count of active users with WebSocket connections."""
        return len(self.active_connections)

# Global connection manager instance
connection_manager = ConnectionManager()
