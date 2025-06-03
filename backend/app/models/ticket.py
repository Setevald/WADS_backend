"""
Ticket-related Pydantic models
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from bson import ObjectId

from app.models.user import PyObjectId, UserProfile


class TicketPriority(str, Enum):
    """Ticket priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, Enum):
    """Ticket status enumeration"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketCategory(str, Enum):
    """Ticket category enumeration"""
    TECHNICAL = "technical"
    BILLING = "billing"
    GENERAL = "general"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    ACCOUNT = "account"


class AttachmentBase(BaseModel):
    """Base attachment model"""
    filename: str
    file_size: int
    content_type: str
    file_path: str


class Attachment(AttachmentBase):
    """Attachment model with metadata"""
    id: PyObjectId = Field(alias="_id")
    uploaded_by: PyObjectId
    uploaded_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class TicketBase(BaseModel):
    """Base ticket model"""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    category: TicketCategory = TicketCategory.GENERAL
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketCreate(TicketBase):
    """Ticket creation model"""
    pass


class TicketUpdate(BaseModel):
    """Ticket update model"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=5000)
    category: Optional[TicketCategory] = None
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    assigned_to: Optional[PyObjectId] = None


class TicketAssign(BaseModel):
    """Ticket assignment model"""
    assigned_to: PyObjectId


class TicketStatusUpdate(BaseModel):
    """Ticket status update model"""
    status: TicketStatus
    resolution_note: Optional[str] = Field(None, max_length=1000)


class TicketResponse(BaseModel):
    """Ticket response model"""
    id: PyObjectId = Field(alias="_id")
    title: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    created_by: Optional[UserProfile] = None
    assigned_to: Optional[UserProfile] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    message_count: int = 0
    attachments: List[Attachment] = []
    tags: List[str] = []
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class TicketSummary(BaseModel):
    """Ticket summary model for listings"""
    id: PyObjectId = Field(alias="_id")
    title: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    created_by: Optional[UserProfile] = None
    assigned_to: Optional[UserProfile] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class TicketFilter(BaseModel):
    """Ticket filtering model"""
    status: Optional[List[TicketStatus]] = None
    priority: Optional[List[TicketPriority]] = None
    category: Optional[List[TicketCategory]] = None
    assigned_to: Optional[List[PyObjectId]] = None
    created_by: Optional[List[PyObjectId]] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    search: Optional[str] = Field(None, max_length=100)


class TicketStats(BaseModel):
    """Ticket statistics model"""
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    high_priority_tickets: int
    urgent_tickets: int
    avg_resolution_time_hours: Optional[float] = None
    tickets_by_category: dict
    tickets_by_agent: dict
    recent_activity: List[dict] = []


class PaginatedTickets(BaseModel):
    """Paginated tickets response"""
    tickets: List[TicketSummary]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool 