"""
Chat and messaging routes for ticket conversations
"""

import math
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Query
from bson import ObjectId

from app.database.connection import get_database
from app.models.user import UserResponse, UserProfile
from app.models.message import (
    MessageCreate, MessageResponse, MessageUpdate, PaginatedMessages,
    ConversationResponse, MessageType, MessageStatus
)
from app.utils.auth import get_current_active_user, check_ticket_permissions

router = APIRouter()


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: MessageCreate,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Send a message in a ticket conversation"""
    # Check if user has permission to access the ticket
    has_permission = await check_ticket_permissions(str(message_data.ticket_id), current_user)
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send messages to this ticket"
        )
    
    db = get_database()
    
    # Create message document
    message_dict = message_data.dict()
    message_dict.update({
        "sender_id": ObjectId(current_user.id),
        "status": MessageStatus.SENT,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_edited": False,
        "edited_at": None,
        "attachments": [],
        "reply_to": None
    })
    
    result = await db.messages.insert_one(message_dict)
    
    # Update ticket message count
    await db.tickets.update_one(
        {"_id": ObjectId(message_data.ticket_id)},
        {
            "$inc": {"message_count": 1},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    # Get the created message with sender info
    created_message = await db.messages.find_one({"_id": result.inserted_id})
    
    # Create sender profile
    sender_profile = UserProfile(
        _id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        department=current_user.department,
        avatar_url=current_user.avatar_url
    )
    
    # Add sender to the message data before creating MessageResponse
    created_message["sender"] = sender_profile
    message_response = MessageResponse(**created_message)
    
    return message_response


@router.get("/tickets/{ticket_id}/messages", response_model=PaginatedMessages)
async def get_ticket_messages(
    ticket_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get messages for a specific ticket"""
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticket ID format"
        )
    
    # Check permissions
    has_permission = await check_ticket_permissions(ticket_id, current_user)
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this ticket's messages"
        )
    
    db = get_database()
    
    # Build query
    query = {"ticket_id": ObjectId(ticket_id)}
    
    # Count total messages
    total = await db.messages.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * per_page
    pages = math.ceil(total / per_page)
    
    # Get messages with sender info
    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": 1}},  # Ascending order for chat
        {"$skip": skip},
        {"$limit": per_page},
        {
            "$lookup": {
                "from": "users",
                "localField": "sender_id",
                "foreignField": "_id",
                "as": "sender_user"
            }
        }
    ]
    
    messages_cursor = db.messages.aggregate(pipeline)
    messages = []
    
    async for message in messages_cursor:
        # Format sender profile
        sender_user = message["sender_user"][0] if message["sender_user"] else None
        
        if sender_user:
            sender = UserProfile(
                _id=sender_user["_id"],
                username=sender_user["username"],
                full_name=sender_user["full_name"],
                role=sender_user["role"],
                department=sender_user.get("department"),
                avatar_url=sender_user.get("avatar_url")
            )
            
            # Add sender to the message data before creating MessageResponse
            message["sender"] = sender
            message_response = MessageResponse(**message)
            
            messages.append(message_response)
    
    return PaginatedMessages(
        messages=messages,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )


@router.get("/tickets/{ticket_id}/conversation", response_model=ConversationResponse)
async def get_ticket_conversation(
    ticket_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get full conversation for a ticket"""
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticket ID format"
        )
    
    # Check permissions
    has_permission = await check_ticket_permissions(ticket_id, current_user)
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this ticket's conversation"
        )
    
    db = get_database()
    
    # Get all messages for the ticket
    pipeline = [
        {"$match": {"ticket_id": ObjectId(ticket_id)}},
        {"$sort": {"created_at": 1}},
        {
            "$lookup": {
                "from": "users",
                "localField": "sender_id",
                "foreignField": "_id",
                "as": "sender_user"
            }
        }
    ]
    
    messages_cursor = db.messages.aggregate(pipeline)
    messages = []
    participants_set = set()
    last_activity = None
    
    async for message in messages_cursor:
        # Format sender profile
        sender_user = message["sender_user"][0] if message["sender_user"] else None
        
        if sender_user:
            sender = UserProfile(
                _id=sender_user["_id"],
                username=sender_user["username"],
                full_name=sender_user["full_name"],
                role=sender_user["role"],
                department=sender_user.get("department"),
                avatar_url=sender_user.get("avatar_url")
            )
            
            # Add sender to the message data before creating MessageResponse
            message["sender"] = sender
            message_response = MessageResponse(**message)
            
            messages.append(message_response)
            participants_set.add(str(sender_user["_id"]))
            last_activity = message["created_at"]
    
    # Get participant profiles
    participants = []
    if participants_set:
        participants_cursor = db.users.find({
            "_id": {"$in": [ObjectId(pid) for pid in participants_set]}
        })
        
        async for user in participants_cursor:
            participants.append(UserProfile(**user))
    
    return ConversationResponse(
        ticket_id=ObjectId(ticket_id),
        messages=messages,
        total_messages=len(messages),
        participants=participants,
        last_activity=last_activity or datetime.utcnow()
    )


@router.put("/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    message_update: MessageUpdate,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Update a message (edit content)"""
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format"
        )
    
    db = get_database()
    
    # Check if message exists and user is the sender
    message = await db.messages.find_one({"_id": ObjectId(message_id)})
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    if str(message["sender_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to edit this message"
        )
    
    # Update message
    update_data = {k: v for k, v in message_update.dict().items() if v is not None}
    update_data.update({
        "updated_at": datetime.utcnow(),
        "edited_at": datetime.utcnow()
    })
    
    await db.messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": update_data}
    )
    
    # Get updated message
    updated_message = await db.messages.find_one({"_id": ObjectId(message_id)})
    
    # Create sender profile
    sender_profile = UserProfile(
        _id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        department=current_user.department,
        avatar_url=current_user.avatar_url
    )
    
    # Add sender to the message data before creating MessageResponse
    updated_message["sender"] = sender_profile
    message_response = MessageResponse(**updated_message)
    
    return message_response


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Delete a message"""
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format"
        )
    
    db = get_database()
    
    # Check if message exists and user is the sender
    message = await db.messages.find_one({"_id": ObjectId(message_id)})
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    if str(message["sender_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this message"
        )
    
    # Delete message
    await db.messages.delete_one({"_id": ObjectId(message_id)})
    
    # Update ticket message count
    await db.tickets.update_one(
        {"_id": message["ticket_id"]},
        {"$inc": {"message_count": -1}}
    ) 