"""
Notification-related Pydantic models
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from bson import ObjectId

from app.models.user import PyObjectId, UserProfile


class NotificationType(str, Enum):
    """Notification type enumeration"""
    TICKET_CREATED = "ticket_created"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    NEW_MESSAGE = "new_message"
    TICKET_RESOLVED = "ticket_resolved"
    SYSTEM_ALERT = "system_alert"
    REMINDER = "reminder"


class NotificationPriority(str, Enum):
    """Notification priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationBase(BaseModel):
    """Base notification model"""
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    metadata: Optional[Dict[str, Any]] = {}


class NotificationCreate(NotificationBase):
    """Notification creation model"""
    user_id: PyObjectId


class NotificationUpdate(BaseModel):
    """Notification update model"""
    is_read: bool = True
    read_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    """Notification response model"""
    id: PyObjectId = Field(alias="_id")
    user_id: PyObjectId
    title: str
    message: str
    notification_type: NotificationType
    priority: NotificationPriority
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime
    metadata: Dict[str, Any] = {}
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class NotificationUserInfo(BaseModel):
    """User information for notification responses"""
    id: str
    username: str
    full_name: str
    role: str


class NotificationSummary(BaseModel):
    """Notification summary model"""
    id: PyObjectId = Field(alias="_id")
    title: str
    message: str
    type: str  # Frontend-friendly type field for icons
    notification_type: NotificationType
    priority: NotificationPriority
    is_read: bool
    created_at: datetime
    user: Optional[NotificationUserInfo] = None  # For admin views
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class NotificationStats(BaseModel):
    """Notification statistics model"""
    total_notifications: int
    unread_count: int
    read_count: int
    by_type: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}


class SystemNotificationStats(BaseModel):
    """System-wide notification statistics for admin dashboard"""
    total_notifications: int
    total_unread: int
    recent_notifications_24h: int
    notifications_by_priority_7d: Dict[str, int]
    notifications_by_type_7d: Dict[str, int]
    top_notification_recipients_7d: List[Dict[str, Any]]
    stats_generated_at: str


class PaginatedNotifications(BaseModel):
    """Paginated notifications response"""
    notifications: List[NotificationSummary]
    total: int
    unread_count: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


class BulkNotificationUpdate(BaseModel):
    """Bulk notification update model"""
    notification_ids: List[PyObjectId]
    is_read: bool = True


class SystemNotificationCreate(BaseModel):
    """System notification creation model"""
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    priority: NotificationPriority = NotificationPriority.HIGH
    target_roles: List[str] = Field(default=["admin", "agent"])


class NotificationCleanupResponse(BaseModel):
    """Notification cleanup response model"""
    dry_run: bool
    notifications_deleted: Optional[int] = None
    notifications_to_delete: Optional[int] = None
    cutoff_date: str
    days_old: int
    message: str 