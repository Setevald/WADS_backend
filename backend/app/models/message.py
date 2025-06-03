"""
Message-related Pydantic models for chat functionality
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId

from app.models.user import PyObjectId, UserProfile
from app.models.ticket import Attachment


class MessageType(str, Enum):
    """Message type enumeration"""
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """Message status enumeration"""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageBase(BaseModel):
    """Base message model"""
    content: str = Field(..., min_length=1, max_length=5000)
    message_type: MessageType = MessageType.TEXT


class MessageCreate(MessageBase):
    """Message creation model"""
    ticket_id: PyObjectId


class MessageUpdate(BaseModel):
    """Message update model"""
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    is_edited: bool = True


class MessageResponse(BaseModel):
    """Message response model"""
    id: PyObjectId = Field(alias="_id")
    ticket_id: PyObjectId
    sender: UserProfile
    content: str
    message_type: MessageType
    status: MessageStatus = MessageStatus.SENT
    created_at: datetime
    updated_at: datetime
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    attachments: List[Attachment] = []
    reply_to: Optional[PyObjectId] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class MessageSummary(BaseModel):
    """Message summary model"""
    id: PyObjectId = Field(alias="_id")
    content: str
    sender: UserProfile
    message_type: MessageType
    created_at: datetime
    attachments_count: int = 0
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class ConversationResponse(BaseModel):
    """Conversation response model"""
    ticket_id: PyObjectId
    messages: List[MessageResponse]
    total_messages: int
    participants: List[UserProfile]
    last_activity: datetime


class PaginatedMessages(BaseModel):
    """Paginated messages response"""
    messages: List[MessageResponse]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


class TypingStatus(BaseModel):
    """Typing status model for real-time features"""
    ticket_id: PyObjectId
    user: UserProfile
    is_typing: bool
    timestamp: datetime 