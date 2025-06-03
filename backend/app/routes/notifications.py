"""
Notification routes for user notifications management
"""

import math
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import RedirectResponse
from bson import ObjectId

from app.database.connection import get_database
from app.models.user import UserResponse, UserRole
from app.models.notification import (
    NotificationCreate, NotificationResponse, NotificationUpdate,
    PaginatedNotifications, NotificationStats, BulkNotificationUpdate,
    NotificationSummary, NotificationType
)
from app.utils.auth import get_current_active_user, get_agent_or_admin_user
from app.services.notification_service import notification_service

router = APIRouter()


@router.get("/", response_model=PaginatedNotifications)
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get user notifications with pagination"""
    db = get_database()
    
    # Build query
    query = {"user_id": ObjectId(current_user.id)}
    if unread_only:
        query["is_read"] = False
    
    # Count total and unread notifications
    total = await db.notifications.count_documents(query)
    unread_count = await db.notifications.count_documents({
        "user_id": ObjectId(current_user.id),
        "is_read": False
    })
    
    # Calculate pagination
    skip = (page - 1) * per_page
    pages = math.ceil(total / per_page)
    
    # Get notifications
    notifications_cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    
    notifications = []
    async for notification in notifications_cursor:
        # Fix notification_type mapping for legacy data
        notification_type = notification.get("notification_type", "")
        if notification_type == "assignment":
            notification_type = "ticket_assigned"
        elif notification_type not in ["ticket_created", "ticket_assigned", "ticket_status_changed", "new_message", "ticket_resolved", "system_alert", "reminder"]:
            notification_type = "system_alert"  # Default fallback
        
        # Set type field for frontend (if missing)
        type_field = notification.get("type", "")
        if not type_field:
            # Map notification_type to frontend type
            type_mapping = {
                "ticket_created": "new_ticket",
                "ticket_assigned": "assignment", 
                "ticket_status_changed": "ticket_update",
                "new_message": "message",
                "ticket_resolved": "ticket_resolved",
                "system_alert": "urgent",
                "reminder": "reminder"
            }
            type_field = type_mapping.get(notification_type, "urgent")
        
        # Create notification summary with fixed data
        notification_data = {
            "_id": notification["_id"],
            "title": notification.get("title", "Notification"),
            "message": notification.get("message", ""),
            "type": type_field,
            "notification_type": notification_type,
            "priority": notification.get("priority", "medium"),
            "is_read": notification.get("is_read", False),
            "created_at": notification.get("created_at", datetime.utcnow())
        }
        
        try:
            notifications.append(NotificationSummary(**notification_data))
        except Exception as e:
            # Log the error but continue processing other notifications
            print(f"Error processing notification {notification.get('_id')}: {e}")
            continue
    
    return PaginatedNotifications(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
        page=page,
        per_page=per_page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )


@router.get("/stats/overview", response_model=NotificationStats)
async def get_notification_stats(current_user: UserResponse = Depends(get_current_active_user)):
    """Get notification statistics for current user"""
    db = get_database()
    
    # Basic counts
    total_notifications = await db.notifications.count_documents({"user_id": ObjectId(current_user.id)})
    unread_count = await db.notifications.count_documents({
        "user_id": ObjectId(current_user.id),
        "is_read": False
    })
    read_count = total_notifications - unread_count
    
    # Notifications by type
    type_pipeline = [
        {"$match": {"user_id": ObjectId(current_user.id)}},
        {"$group": {"_id": "$notification_type", "count": {"$sum": 1}}}
    ]
    type_results = await db.notifications.aggregate(type_pipeline).to_list(None)
    by_type = {result["_id"]: result["count"] for result in type_results}
    
    # Notifications by priority
    priority_pipeline = [
        {"$match": {"user_id": ObjectId(current_user.id)}},
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
    ]
    priority_results = await db.notifications.aggregate(priority_pipeline).to_list(None)
    by_priority = {result["_id"]: result["count"] for result in priority_results}
    
    return NotificationStats(
        total_notifications=total_notifications,
        unread_count=unread_count,
        read_count=read_count,
        by_type=by_type,
        by_priority=by_priority
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get a specific notification"""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification ID format"
        )
    
    db = get_database()
    
    notification = await db.notifications.find_one({
        "_id": ObjectId(notification_id),
        "user_id": ObjectId(current_user.id)
    })
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return NotificationResponse(**notification)


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Mark a notification as read"""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification ID format"
        )
    
    db = get_database()
    
    result = await db.notifications.update_one(
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
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}


@router.put("/admin/{notification_id}/read")
async def mark_notification_read_admin(
    notification_id: str,
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Mark any notification as read (admin/agent only)"""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification ID format"
        )
    
    db = get_database()
    
    # Admin can mark any notification as read (no user_id filter)
    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.utcnow()
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}


@router.post("/mark-all-read")
async def mark_all_notifications_read(current_user: UserResponse = Depends(get_current_active_user)):
    """Mark all user notifications as read"""
    db = get_database()
    
    await db.notifications.update_many(
        {"user_id": ObjectId(current_user.id), "is_read": False},
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "All notifications marked as read"}


@router.post("/bulk-update")
async def bulk_update_notifications(
    bulk_update: BulkNotificationUpdate,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Bulk update notifications"""
    db = get_database()
    
    notification_ids = [ObjectId(nid) for nid in bulk_update.notification_ids]
    
    update_data = {"is_read": bulk_update.is_read}
    if bulk_update.is_read:
        update_data["read_at"] = datetime.utcnow()
    
    result = await db.notifications.update_many(
        {
            "_id": {"$in": notification_ids},
            "user_id": ObjectId(current_user.id)
        },
        {"$set": update_data}
    )
    
    return {"message": f"Updated {result.modified_count} notifications"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Delete a notification"""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification ID format"
        )
    
    db = get_database()
    
    result = await db.notifications.delete_one({
        "_id": ObjectId(notification_id),
        "user_id": ObjectId(current_user.id)
    })
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification deleted"}


@router.post("/create", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_data: NotificationCreate,
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Create a notification (admin/agent only)"""
    db = get_database()
    
    # Create notification document
    notification_dict = notification_data.dict()
    notification_dict.update({
        "is_read": False,
        "read_at": None,
        "created_at": datetime.utcnow()
    })
    
    result = await db.notifications.insert_one(notification_dict)
    created_notification = await db.notifications.find_one({"_id": result.inserted_id})
    
    return NotificationResponse(**created_notification)


# Admin-specific endpoints
@router.get("/admin/all", response_model=PaginatedNotifications)
async def get_all_notifications_admin(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = Query(None),
    notification_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    days_back: Optional[int] = Query(None, ge=1, le=365),
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Get all notifications for admin dashboard with advanced filtering"""
    db = get_database()
    
    # Build query
    query = {}
    
    # Filter by user if specified
    if user_id:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )
        query["user_id"] = ObjectId(user_id)
    
    # Filter by notification type
    if notification_type:
        query["notification_type"] = notification_type
    
    # Filter by priority
    if priority:
        query["priority"] = priority
    
    # Filter by read status
    if unread_only:
        query["is_read"] = False
    
    # Filter by date range
    if days_back:
        start_date = datetime.utcnow() - timedelta(days=days_back)
        query["created_at"] = {"$gte": start_date}
    
    # Count total notifications
    total = await db.notifications.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * per_page
    pages = math.ceil(total / per_page)
    
    # Get notifications with user info
    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": per_page},
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user_info"
            }
        }
    ]
    
    notifications_cursor = db.notifications.aggregate(pipeline)
    notifications = []
    
    async for notification in notifications_cursor:
        user_info = notification["user_info"][0] if notification["user_info"] else {}
        
        # Add user info to notification data
        notification_data = {
            "_id": notification["_id"],
            "title": notification.get("title", "Notification"),
            "message": notification.get("message", ""),
            "type": notification.get("type", "system"),
            "notification_type": notification.get("notification_type", "system_alert"),
            "priority": notification.get("priority", "medium"),
            "is_read": notification.get("is_read", False),
            "created_at": notification.get("created_at", datetime.utcnow()),
            "user": {
                "id": str(user_info.get("_id", "")),
                "username": user_info.get("username", ""),
                "full_name": user_info.get("full_name", ""),
                "role": user_info.get("role", "")
            } if user_info else None
        }
        
        try:
            notifications.append(NotificationSummary(**notification_data))
        except Exception as e:
            print(f"Error processing notification {notification.get('_id')}: {e}")
            continue
    
    # Get unread count for context
    unread_count = await db.notifications.count_documents({**query, "is_read": False})
    
    return PaginatedNotifications(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
        page=page,
        per_page=per_page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )


@router.post("/admin/system-alert")
async def create_system_notification(
    title: str = Query(..., description="Notification title"),
    message: str = Query(..., description="Notification message"),
    priority: str = Query("high", description="Notification priority: low, medium, high, urgent"),
    target_roles: List[str] = Query(["admin", "agent"], description="Target user roles"),
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Create system-wide notification for specific user roles"""
    db = get_database()
    
    # Validate priority
    valid_priorities = ["low", "medium", "high", "urgent"]
    if priority not in valid_priorities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Priority must be one of: {valid_priorities}"
        )
    
    # Validate target roles
    valid_roles = ["customer", "agent", "admin"]
    invalid_roles = [role for role in target_roles if role not in valid_roles]
    if invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid roles: {invalid_roles}. Valid roles are: {valid_roles}"
        )
    
    # Get users with target roles
    target_users = await db.users.find({
        "role": {"$in": target_roles},
        "is_active": True
    }).to_list(None)
    
    if not target_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active users found with specified roles"
        )
    
    # Create notifications for each target user
    created_notifications = []
    for user in target_users:
        notification_response = await notification_service.create_and_broadcast_notification(
            user_id=str(user["_id"]),
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            message=message,
            data={
                "system_alert": True,
                "created_by": {
                    "id": str(current_user.id),
                    "username": current_user.username,
                    "full_name": current_user.full_name
                }
            },
            priority=priority
        )
        created_notifications.append(notification_response)
    
    return {
        "message": f"System notification sent to {len(created_notifications)} users",
        "target_count": len(created_notifications),
        "target_roles": target_roles,
        "notification_id_sample": str(created_notifications[0].id) if created_notifications else None
    }


@router.get("/admin/stats/system", response_model=dict)
async def get_system_notification_stats(
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Get system-wide notification statistics for admin dashboard"""
    db = get_database()
    
    # Overall counts
    total_notifications = await db.notifications.count_documents({})
    total_unread = await db.notifications.count_documents({"is_read": False})
    
    # Notifications in last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_notifications = await db.notifications.count_documents({
        "created_at": {"$gte": yesterday}
    })
    
    # Notifications by priority (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    priority_pipeline = [
        {"$match": {"created_at": {"$gte": week_ago}}},
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
    ]
    priority_results = await db.notifications.aggregate(priority_pipeline).to_list(None)
    notifications_by_priority = {result["_id"]: result["count"] for result in priority_results}
    
    # Notifications by type (last 7 days)
    type_pipeline = [
        {"$match": {"created_at": {"$gte": week_ago}}},
        {"$group": {"_id": "$notification_type", "count": {"$sum": 1}}}
    ]
    type_results = await db.notifications.aggregate(type_pipeline).to_list(None)
    notifications_by_type = {result["_id"]: result["count"] for result in type_results}
    
    # Top users by notification count (last 7 days)
    user_pipeline = [
        {"$match": {"created_at": {"$gte": week_ago}}},
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user_info"
            }
        },
        {"$unwind": "$user_info"},
        {
            "$group": {
                "_id": "$user_id",
                "count": {"$sum": 1},
                "username": {"$first": "$user_info.username"},
                "full_name": {"$first": "$user_info.full_name"},
                "role": {"$first": "$user_info.role"}
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    user_results = await db.notifications.aggregate(user_pipeline).to_list(None)
    top_notification_recipients = [
        {
            "user_id": str(result["_id"]),
            "username": result["username"],
            "full_name": result["full_name"],
            "role": result["role"],
            "notification_count": result["count"]
        }
        for result in user_results
    ]
    
    return {
        "total_notifications": total_notifications,
        "total_unread": total_unread,
        "recent_notifications_24h": recent_notifications,
        "notifications_by_priority_7d": notifications_by_priority,
        "notifications_by_type_7d": notifications_by_type,
        "top_notification_recipients_7d": top_notification_recipients,
        "stats_generated_at": datetime.utcnow().isoformat()
    }


@router.delete("/admin/cleanup")
async def cleanup_old_notifications(
    days_old: int = Query(30, ge=7, le=365, description="Delete notifications older than X days"),
    dry_run: bool = Query(True, description="Preview what would be deleted without actually deleting"),
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Clean up old read notifications (admin only)"""
    db = get_database()
    
    # Only allow admins to perform cleanup
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform notification cleanup"
        )
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    
    # Query for old read notifications
    cleanup_query = {
        "is_read": True,
        "created_at": {"$lt": cutoff_date}
    }
    
    # Count what would be deleted
    count_to_delete = await db.notifications.count_documents(cleanup_query)
    
    if dry_run:
        return {
            "dry_run": True,
            "notifications_to_delete": count_to_delete,
            "cutoff_date": cutoff_date.isoformat(),
            "days_old": days_old,
            "message": f"Would delete {count_to_delete} read notifications older than {days_old} days"
        }
    
    # Perform actual deletion
    if count_to_delete > 0:
        result = await db.notifications.delete_many(cleanup_query)
        deleted_count = result.deleted_count
    else:
        deleted_count = 0
    
    return {
        "dry_run": False,
        "notifications_deleted": deleted_count,
        "cutoff_date": cutoff_date.isoformat(),
        "days_old": days_old,
        "message": f"Successfully deleted {deleted_count} old notifications"
    } 