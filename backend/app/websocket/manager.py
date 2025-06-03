"""
WebSocket connection manager for real-time functionality
"""

import json
import logging
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from bson import ObjectId

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manager for WebSocket connections with user and admin segregation"""
    
    def __init__(self):
        # Store active connections by user ID
        self.active_connections: Dict[str, WebSocket] = {}
        # Store admin connections separately for admin-specific broadcasts
        self.admin_connections: Set[str] = set()
        # Store user roles for proper routing
        self.user_roles: Dict[str, str] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, user_role: str):
        """Accept and store a WebSocket connection (legacy method)"""
        await websocket.accept()
        await self.register_connection(websocket, user_id, user_role)
    
    async def register_connection(self, websocket: WebSocket, user_id: str, user_role: str):
        """Register a WebSocket connection (connection should already be accepted)"""
        # If user already connected, disconnect old connection first
        if user_id in self.active_connections:
            logger.info(f"User {user_id} already connected, replacing connection")
            old_websocket = self.active_connections[user_id]
            try:
                await old_websocket.close(code=1000, reason="New connection established")
            except Exception as e:
                logger.warning(f"Could not close old connection for user {user_id}: {e}")
        
        self.active_connections[user_id] = websocket
        self.user_roles[user_id] = user_role
        
        if user_role in ["admin", "agent"]:
            self.admin_connections.add(user_id)
        
        logger.info(f"User {user_id} ({user_role}) registered via WebSocket")
    
    def disconnect(self, user_id: str):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.admin_connections:
            self.admin_connections.remove(user_id)
        if user_id in self.user_roles:
            del self.user_roles[user_id]
        
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """Send a message to a specific user"""
        if user_id in self.active_connections:
            try:
                websocket = self.active_connections[user_id]
                # Check if websocket is still open
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_text(json.dumps(message))
                else:
                    logger.warning(f"WebSocket for user {user_id} is not connected, removing")
                    self.disconnect(user_id)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                # Remove disconnected connection
                self.disconnect(user_id)
    
    async def broadcast_to_admins(self, message: Dict[str, Any]):
        """Send a message to all connected admins and agents"""
        disconnected_users = []
        
        for user_id in self.admin_connections.copy():  # Use copy to avoid modification during iteration
            if user_id in self.active_connections:
                try:
                    websocket = self.active_connections[user_id]
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_text(json.dumps(message))
                    else:
                        disconnected_users.append(user_id)
                except Exception as e:
                    logger.error(f"Error broadcasting to admin {user_id}: {e}")
                    disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Send a message to all connected users"""
        disconnected_users = []
        
        for user_id, websocket in self.active_connections.copy().items():  # Use copy to avoid modification during iteration
            try:
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_text(json.dumps(message))
                else:
                    disconnected_users.append(user_id)
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    async def send_notification(self, notification_data: Dict[str, Any], target_user_id: str):
        """Send a notification to a specific user"""
        message = {
            "type": "notification",
            "data": notification_data
        }
        await self.send_personal_message(message, target_user_id)
    
    async def send_ticket_update(self, ticket_data: Dict[str, Any], user_ids: List[str] = None):
        """Send ticket update to relevant users"""
        message = {
            "type": "ticket_update", 
            "data": ticket_data
        }
        
        if user_ids:
            # Send to specific users
            for user_id in user_ids:
                await self.send_personal_message(message, user_id)
        else:
            # Broadcast to all admins/agents
            await self.broadcast_to_admins(message)
    
    async def send_new_ticket_alert(self, ticket_data: Dict[str, Any]):
        """Send new ticket alert to all admins and agents"""
        message = {
            "type": "new_ticket",
            "data": ticket_data
        }
        await self.broadcast_to_admins(message)
    
    def get_connected_users(self) -> List[str]:
        """Get list of connected user IDs"""
        return list(self.active_connections.keys())
    
    def get_connected_admins(self) -> List[str]:
        """Get list of connected admin/agent user IDs"""
        return list(self.admin_connections)
    
    def is_user_connected(self, user_id: str) -> bool:
        """Check if a user is currently connected"""
        return user_id in self.active_connections
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get detailed connection information"""
        return {
            "total_connections": len(self.active_connections),
            "admin_connections": len(self.admin_connections),
            "customer_connections": len(self.active_connections) - len(self.admin_connections),
            "connected_users": list(self.active_connections.keys()),
            "connected_admins": list(self.admin_connections),
            "user_roles": self.user_roles.copy()
        }


# Global connection manager instance
manager = ConnectionManager() 