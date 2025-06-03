"""
Notification service for creating and broadcasting notifications
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId

from app.database.connection import get_database
from app.models.notification import NotificationType, NotificationCreate, NotificationResponse
from app.models.user import UserRole
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications and real-time broadcasting"""
    
    @staticmethod
    async def create_and_broadcast_notification(
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        ticket_id: Optional[str] = None,
        priority: str = "medium"
    ) -> NotificationResponse:
        """Create a notification and broadcast it via WebSocket"""
        try:
            db = get_database()
            
            # Create notification document
            notification_data = {
                "user_id": ObjectId(user_id),
                "notification_type": notification_type.value,
                "title": title,
                "message": message,
                "data": data or {},
                "ticket_id": ObjectId(ticket_id) if ticket_id else None,
                "priority": priority,
                "is_read": False,
                "read_at": None,
                "created_at": datetime.utcnow()
            }
            
            # Insert notification
            result = await db.notifications.insert_one(notification_data)
            created_notification = await db.notifications.find_one({"_id": result.inserted_id})
            
            # Convert ObjectIds to strings for proper serialization
            notification_for_response = created_notification.copy()
            notification_for_response["_id"] = str(created_notification["_id"])
            notification_for_response["user_id"] = str(created_notification["user_id"])
            if notification_for_response.get("ticket_id"):
                notification_for_response["ticket_id"] = str(created_notification["ticket_id"])
            
            # Prepare notification response
            notification_response = NotificationResponse(**notification_for_response)
            
            # Broadcast via WebSocket if user is connected
            if manager.is_user_connected(user_id):
                # Convert to dict and ensure all ObjectIds are strings
                websocket_data = notification_response.dict()
                websocket_data["_id"] = str(notification_response.id)
                websocket_data["id"] = str(notification_response.id)  # Add both _id and id for compatibility
                
                await manager.send_notification(
                    websocket_data,
                    user_id
                )
                logger.info(f"Sent WebSocket notification to user {user_id}")
            else:
                logger.info(f"User {user_id} not connected, notification saved to database only")
            
            logger.info(f"Created and broadcast notification {result.inserted_id} to user {user_id}")
            return notification_response
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise
    
    @staticmethod
    async def create_ticket_notification(
        ticket_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        target_user_id: Optional[str] = None,
        notify_all_admins: bool = False
    ):
        """Create ticket-related notifications"""
        try:
            db = get_database()
            
            # Get ticket details
            ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return
            
            # Determine who to notify
            users_to_notify = []
            
            if notify_all_admins:
                # Notify all admins and agents
                admin_users = await db.users.find({
                    "role": {"$in": ["admin", "agent"]},
                    "is_active": True
                }).to_list(None)
                users_to_notify.extend([str(user["_id"]) for user in admin_users])
            
            if target_user_id:
                users_to_notify.append(target_user_id)
            
            # If no specific target, notify ticket creator
            if not users_to_notify:
                users_to_notify.append(str(ticket["created_by"]))
            
            # Create notifications for each user
            for user_id in set(users_to_notify):  # Remove duplicates
                await NotificationService.create_and_broadcast_notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    data={
                        "ticket_id": ticket_id,
                        "ticket_title": ticket.get("title", ""),
                        "ticket_status": ticket.get("status", ""),
                        "ticket_priority": ticket.get("priority", "medium")
                    },
                    ticket_id=ticket_id
                )
            
            # Broadcast ticket update to connected users
            ticket_data = {
                "id": ticket_id,
                "subject": ticket.get("title", ""),
                "status": ticket.get("status", ""),
                "priority": ticket.get("priority", "medium"),
                "updated_at": datetime.utcnow().isoformat(),
                "update_type": notification_type.value
            }
            
            # Send to specific users and admins
            await manager.send_ticket_update(ticket_data, users_to_notify)
            
        except Exception as e:
            logger.error(f"Error creating ticket notification: {e}")
    
    @staticmethod
    async def notify_new_ticket(ticket_id: str):
        """Notify admins about a new ticket"""
        try:
            db = get_database()
            
            # Get ticket details with creator info
            pipeline = [
                {"$match": {"_id": ObjectId(ticket_id)}},
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "created_by",
                        "foreignField": "_id",
                        "as": "creator"
                    }
                }
            ]
            
            ticket_cursor = db.tickets.aggregate(pipeline)
            ticket_data = await ticket_cursor.to_list(length=1)
            
            if not ticket_data:
                logger.error(f"Ticket {ticket_id} not found")
                return
            
            ticket = ticket_data[0]
            creator = ticket["creator"][0] if ticket["creator"] else {}
            
            title = f"New {ticket.get('priority', 'medium').title()} Priority Ticket"
            message = f"New ticket '{ticket.get('title', '')}' submitted by {creator.get('full_name', 'Unknown User')}"
            
            # Create notifications for all admins/agents
            await NotificationService.create_ticket_notification(
                ticket_id=ticket_id,
                notification_type=NotificationType.TICKET_CREATED,
                title=title,
                message=message,
                notify_all_admins=True
            )
            
            # Broadcast new ticket alert
            ticket_alert_data = {
                "id": ticket_id,
                "title": ticket.get("title", ""),
                "priority": ticket.get("priority", "medium"),
                "status": ticket.get("status", ""),
                "created_by": {
                    "id": str(creator.get("_id", "")),
                    "name": creator.get("full_name", "Unknown User"),
                    "email": creator.get("email", "")
                },
                "created_at": ticket.get("created_at", datetime.utcnow()).isoformat()
            }
            
            await manager.send_new_ticket_alert(ticket_alert_data)
            
        except Exception as e:
            logger.error(f"Error notifying new ticket: {e}")
    
    @staticmethod
    async def notify_ticket_assignment(ticket_id: str, assigned_to_id: str, assigned_by_id: str):
        """Notify about ticket assignment"""
        try:
            db = get_database()
            
            # Get assignee and assigner details
            assignee = await db.users.find_one({"_id": ObjectId(assigned_to_id)})
            assigner = await db.users.find_one({"_id": ObjectId(assigned_by_id)})
            ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
            
            if not all([assignee, assigner, ticket]):
                logger.error("Missing data for ticket assignment notification")
                return
            
            title = "New Ticket Assignment"
            message = f"You have been assigned ticket '{ticket.get('title', '')}' by {assigner.get('full_name', 'Admin')}"
            
            await NotificationService.create_and_broadcast_notification(
                user_id=assigned_to_id,
                notification_type=NotificationType.TICKET_ASSIGNED,
                title=title,
                message=message,
                data={
                    "ticket_id": ticket_id,
                    "ticket_title": ticket.get("title", ""),
                    "ticket_status": ticket.get("status", ""),
                    "ticket_priority": ticket.get("priority", "medium"),
                    "assigned_by": {
                        "id": assigned_by_id,
                        "name": assigner.get("full_name", ""),
                        "username": assigner.get("username", "")
                    }
                },
                ticket_id=ticket_id
            )
            
        except Exception as e:
            logger.error(f"Error notifying ticket assignment: {e}")
    
    @staticmethod
    async def notify_ticket_status_change(ticket_id: str, old_status: str, new_status: str, updated_by_id: str):
        """Notify about ticket status changes"""
        try:
            db = get_database()
            
            ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
            updated_by = await db.users.find_one({"_id": ObjectId(updated_by_id)})
            
            if not all([ticket, updated_by]):
                logger.error("Missing data for ticket status change notification")
                return
            
            title = f"Ticket Status Updated: {new_status.title()}"
            message = f"Ticket '{ticket.get('title', '')}' status changed from {old_status} to {new_status}"
            
            # Notify ticket creator
            creator_id = str(ticket["created_by"])
            await NotificationService.create_and_broadcast_notification(
                user_id=creator_id,
                notification_type=NotificationType.TICKET_STATUS_CHANGED,
                title=title,
                message=message,
                data={
                    "ticket_id": ticket_id,
                    "ticket_title": ticket.get("title", ""),
                    "old_status": old_status,
                    "new_status": new_status,
                    "updated_by": {
                        "id": updated_by_id,
                        "name": updated_by.get("full_name", ""),
                        "username": updated_by.get("username", "")
                    }
                },
                ticket_id=ticket_id
            )
            
            # If ticket is assigned, also notify the assignee (if different from creator)
            if ticket.get("assigned_to") and str(ticket["assigned_to"]) != creator_id:
                await NotificationService.create_and_broadcast_notification(
                    user_id=str(ticket["assigned_to"]),
                    notification_type=NotificationType.TICKET_STATUS_CHANGED,
                    title=title,
                    message=message,
                    data={
                        "ticket_id": ticket_id,
                        "ticket_title": ticket.get("title", ""),
                        "old_status": old_status,
                        "new_status": new_status,
                        "updated_by": {
                            "id": updated_by_id,
                            "name": updated_by.get("full_name", ""),
                            "username": updated_by.get("username", "")
                        }
                    },
                    ticket_id=ticket_id
                )
            
        except Exception as e:
            logger.error(f"Error notifying ticket status change: {e}")
    
    @staticmethod
    async def notify_ticket_resolved(ticket_id: str, resolved_by_id: str, resolution_note: Optional[str] = None):
        """Notify about ticket resolution"""
        try:
            db = get_database()
            
            ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
            resolved_by = await db.users.find_one({"_id": ObjectId(resolved_by_id)})
            
            if not all([ticket, resolved_by]):
                logger.error("Missing data for ticket resolution notification")
                return
            
            title = "Ticket Resolved"
            message = f"Your ticket '{ticket.get('title', '')}' has been resolved by {resolved_by.get('full_name', 'Support Agent')}"
            
            if resolution_note:
                message += f". Resolution: {resolution_note}"
            
            # Notify ticket creator
            await NotificationService.create_and_broadcast_notification(
                user_id=str(ticket["created_by"]),
                notification_type=NotificationType.TICKET_RESOLVED,
                title=title,
                message=message,
                data={
                    "ticket_id": ticket_id,
                    "ticket_title": ticket.get("title", ""),
                    "ticket_status": ticket.get("status", ""),
                    "ticket_priority": ticket.get("priority", "medium"),
                    "resolution_note": resolution_note,
                    "resolved_by": {
                        "id": resolved_by_id,
                        "name": resolved_by.get("full_name", ""),
                        "username": resolved_by.get("username", "")
                    }
                },
                ticket_id=ticket_id,
                priority="high"
            )
            
        except Exception as e:
            logger.error(f"Error notifying ticket resolution: {e}")


# Create service instance
notification_service = NotificationService() 