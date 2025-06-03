"""
WebSocket routes for real-time functionality
"""

import json
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from jose import JWTError, jwt
from bson import ObjectId

from app.config import settings
from app.models.user import UserResponse, UserRole
from app.websocket.manager import manager
from app.database.connection import get_database

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_current_user_websocket(token: str) -> UserResponse:
    """Get current user from WebSocket token parameter"""
    try:
        # Validate token format first
        if not token or token.count('.') != 2:
            logger.error(f"Invalid JWT token format: expected 3 segments, got {token.count('.') + 1 if token else 0}")
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Decode JWT token
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            logger.error("No user ID found in JWT token")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user from database
        db = get_database()
        
        # User ID in JWT token is already a string representation of ObjectId
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except Exception as e:
            logger.error(f"Error finding user {user_id}: {e}")
            user = None
        
        if user is None:
            logger.error(f"User {user_id} not found in database")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check user status (not is_active)
        if user.get("status") != "active":
            logger.error(f"User {user_id} is not active (status: {user.get('status')})")
            raise HTTPException(status_code=400, detail="Inactive user")
        
        # Convert ObjectId fields to strings for response
        user_data = user.copy()
        user_data["_id"] = str(user["_id"])
        if user_data.get("department"):
            user_data["department"] = str(user_data["department"])
        
        return UserResponse(**user_data)
        
    except JWTError as e:
        logger.error(f"JWT error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error in websocket auth: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time notifications and updates
    Requires authentication via JWT token in query parameter
    """
    current_user = None
    connection_accepted = False
    
    try:
        logger.info(f"WebSocket connection attempt with token: {token[:20]}..." if token else "No token")
        
        # Accept the WebSocket connection first (ASGI requirement)
        await websocket.accept()
        connection_accepted = True
        logger.debug("WebSocket connection accepted")
        
        # Now authenticate user
        try:
            current_user = await get_current_user_websocket(token)
            logger.info(f"WebSocket authentication successful for user: {current_user.username} ({current_user.role})")
        except HTTPException as auth_error:
            logger.error(f"WebSocket authentication failed: {auth_error.detail}")
            # Send authentication error and close connection properly
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {
                    "message": auth_error.detail,
                    "code": auth_error.status_code
                }
            }))
            await websocket.close(code=1008)  # Policy violation
            return
        
        # Register user with connection manager
        await manager.register_connection(websocket, str(current_user.id), current_user.role.value)
        logger.info(f"WebSocket connection registered for user: {current_user.username}")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "data": {
                "user_id": str(current_user.id),
                "username": current_user.username,
                "role": current_user.role.value,
                "message": "WebSocket connection established successfully"
            }
        }))
        
        try:
            # Keep connection alive and handle incoming messages
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                logger.debug(f"Received WebSocket message from {current_user.username}: {message.get('type')}")
                
                # Handle ping/pong for connection health
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    }))
                
                # Handle message read receipts
                elif message.get("type") == "mark_notification_read":
                    notification_id = message.get("notification_id")
                    if notification_id:
                        await handle_notification_read(notification_id, current_user)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user: {current_user.username if current_user else 'Unknown'}")
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        import traceback
        logger.error(f"WebSocket traceback: {traceback.format_exc()}")
        
        if connection_accepted:
            try:
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "data": {
                        "message": "Internal server error",
                        "code": 500
                    }
                }))
                await websocket.close(code=1011)  # Internal error
            except Exception as close_error:
                logger.error(f"Error closing WebSocket after exception: {close_error}")
        
    finally:
        # Clean up connection
        try:
            if current_user:
                manager.disconnect(str(current_user.id))
                logger.info(f"WebSocket cleanup completed for user: {current_user.username}")
        except Exception as cleanup_error:
            logger.error(f"Error during WebSocket cleanup: {cleanup_error}")


async def handle_notification_read(notification_id: str, current_user: UserResponse):
    """Handle marking notification as read via WebSocket"""
    try:
        from bson import ObjectId
        db = get_database()
        
        # Update notification as read
        await db.notifications.update_one(
            {
                "_id": ObjectId(notification_id),
                "user_id": ObjectId(current_user.id)
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.utcnow()
                }
            }
        )
        
        # Send confirmation back to user
        await manager.send_personal_message({
            "type": "notification_read_confirmed",
            "data": {
                "notification_id": notification_id
            }
        }, str(current_user.id))
        
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")


@router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics (admin only)"""
    return {
        "connected_users": manager.get_connected_users(),
        "connected_admins": manager.get_connected_admins(),
        "total_connections": len(manager.get_connected_users())
    } 