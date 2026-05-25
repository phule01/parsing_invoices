from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.orm import Session
import logging
from database import get_db
from app.core.security import decode_token
from websocket_manager import connection_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ws", tags=["websocket"])

@router.websocket("/updates")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time updates.
    Connects to receive real-time notifications for invoice and product changes.
    """
    try:
        # Verify token and get user ID
        token_data = decode_token(token)
        user_id = token_data["user_id"]
        
        # Register connection
        await connection_manager.connect(websocket, user_id)
        logger.info(f"WebSocket connected for user {user_id}")
        
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to real-time updates",
            "user_id": user_id,
            "active_users": connection_manager.get_active_user_count()
        })
        
        # Keep connection open and listen for messages
        while True:
            # Receive any incoming message (ping, keep-alive, etc.)
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "keep-alive":
                await websocket.send_json({"type": "keep-alive", "status": "alive"})
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected (user {user_id})")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        # Disconnect and cleanup
        await connection_manager.disconnect(user_id, websocket)
        logger.info(f"WebSocket disconnected for user {user_id}")