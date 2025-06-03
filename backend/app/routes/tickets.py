"""
Ticket management routes for CRUD operations
"""

import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from bson import ObjectId

from app.config import settings
from app.database.connection import get_database
from app.models.user import UserResponse, UserRole, UserProfile
from app.models.ticket import (
    TicketCreate, TicketUpdate, TicketResponse, TicketSummary,
    TicketAssign, TicketStatusUpdate, PaginatedTickets, TicketStats,
    TicketStatus, TicketPriority, TicketCategory
)
from app.utils.auth import get_current_active_user, get_agent_or_admin_user, check_ticket_permissions
from app.services.notification_service import notification_service

router = APIRouter()


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_data: TicketCreate,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Create a new support ticket"""
    db = get_database()
    
    # Create ticket document
    ticket_dict = ticket_data.dict()
    ticket_dict.update({
        "created_by": ObjectId(current_user.id),
        "status": TicketStatus.OPEN,
        "assigned_to": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "resolved_at": None,
        "resolution_note": None,
        "message_count": 0,
        "attachments": [],
        "tags": []
    })
    
    result = await db.tickets.insert_one(ticket_dict)
    created_ticket = await db.tickets.find_one({"_id": result.inserted_id})
    
    # Get user profile for response
    user_profile = UserProfile(
        _id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        department=current_user.department,
        avatar_url=current_user.avatar_url
    )
    
    # Prepare ticket response data with user profile
    ticket_response_data = created_ticket.copy()
    ticket_response_data.pop("created_by", None)  # Remove the ObjectId version
    ticket_response_data["created_by"] = user_profile  # Add the UserProfile version
    
    # Format response
    ticket_response = TicketResponse(**ticket_response_data)
    
    # Send real-time notifications to admins/agents about new ticket
    await notification_service.notify_new_ticket(str(result.inserted_id))
    
    return ticket_response


@router.get("/", response_model=PaginatedTickets)
async def get_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get paginated list of tickets"""
    db = get_database()
    
    # Build query filter
    query = {}
    
    # For customers, only show their tickets
    if current_user.role == UserRole.CUSTOMER:
        query["created_by"] = ObjectId(current_user.id)
    
    # Add filters
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if category:
        query["category"] = category
    if search:
        query["$text"] = {"$search": search}
    
    # Count total tickets
    total = await db.tickets.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * per_page
    pages = math.ceil(total / per_page)
    
    # Get tickets with user data
    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": per_page},
        {
            "$lookup": {
                "from": "users",
                "localField": "created_by",
                "foreignField": "_id",
                "as": "created_by_user"
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_to",
                "foreignField": "_id",
                "as": "assigned_to_user"
            }
        }
    ]
    
    tickets_cursor = db.tickets.aggregate(pipeline)
    tickets = []
    
    async for ticket in tickets_cursor:
        # Format user profiles
        created_by_user = ticket["created_by_user"][0] if ticket["created_by_user"] else None
        assigned_to_user = ticket["assigned_to_user"][0] if ticket["assigned_to_user"] else None
        
        created_by = UserProfile(
            _id=created_by_user["_id"],
            username=created_by_user["username"],
            full_name=created_by_user["full_name"],
            role=created_by_user["role"],
            department=created_by_user.get("department"),
            avatar_url=created_by_user.get("avatar_url")
        ) if created_by_user else None
        
        assigned_to = UserProfile(
            _id=assigned_to_user["_id"],
            username=assigned_to_user["username"],
            full_name=assigned_to_user["full_name"],
            role=assigned_to_user["role"],
            department=assigned_to_user.get("department"),
            avatar_url=assigned_to_user.get("avatar_url")
        ) if assigned_to_user else None
        
        # Create ticket summary data excluding user fields that need special formatting
        ticket_data = {k: v for k, v in ticket.items() if k not in ["created_by_user", "assigned_to_user", "created_by", "assigned_to"]}
        
        # Add the properly formatted user profiles
        ticket_data["created_by"] = created_by
        ticket_data["assigned_to"] = assigned_to
        
        ticket_summary = TicketSummary(**ticket_data)
        
        tickets.append(ticket_summary)
    
    return PaginatedTickets(
        tickets=tickets,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get a specific ticket by ID"""
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
            detail="Not authorized to access this ticket"
        )
    
    db = get_database()
    
    # Get ticket with user data
    pipeline = [
        {"$match": {"_id": ObjectId(ticket_id)}},
        {
            "$lookup": {
                "from": "users",
                "localField": "created_by",
                "foreignField": "_id",
                "as": "created_by_user"
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_to",
                "foreignField": "_id",
                "as": "assigned_to_user"
            }
        }
    ]
    
    result = await db.tickets.aggregate(pipeline).to_list(1)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    ticket = result[0]
    
    # Format user profiles
    created_by_user = ticket["created_by_user"][0] if ticket["created_by_user"] else None
    assigned_to_user = ticket["assigned_to_user"][0] if ticket["assigned_to_user"] else None
    
    created_by = UserProfile(**created_by_user) if created_by_user else None
    assigned_to = UserProfile(**assigned_to_user) if assigned_to_user else None
    
    # Create ticket response data excluding user fields that need special formatting
    ticket_data = {k: v for k, v in ticket.items() if k not in ["created_by_user", "assigned_to_user", "created_by", "assigned_to"]}
    
    # Add the properly formatted user profiles
    ticket_data["created_by"] = created_by
    ticket_data["assigned_to"] = assigned_to
    
    ticket_response = TicketResponse(**ticket_data)
    
    return ticket_response


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: str,
    ticket_update: TicketUpdate,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Update a ticket"""
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
            detail="Not authorized to update this ticket"
        )
    
    db = get_database()
    
    # Get original ticket for comparison
    original_ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if not original_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Prepare update data
    update_data = {k: v for k, v in ticket_update.dict().items() if v is not None}
    
    if not update_data:
        return await get_ticket(ticket_id, current_user)
    
    update_data["updated_at"] = datetime.utcnow()
    
    # Track status changes for notifications
    old_status = original_ticket.get("status")
    new_status = update_data.get("status")
    
    # If status is being changed to resolved, set resolved_at
    if new_status == TicketStatus.RESOLVED:
        update_data["resolved_at"] = datetime.utcnow()
    
    result = await db.tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Send notifications for status changes
    if new_status and old_status != new_status:
        if new_status == TicketStatus.RESOLVED:
            # Special notification for resolution
            await notification_service.notify_ticket_resolved(
                ticket_id, 
                str(current_user.id),
                update_data.get("resolution_note")
            )
        else:
            # General status change notification
            await notification_service.notify_ticket_status_change(
                ticket_id,
                old_status,
                new_status,
                str(current_user.id)
            )
    
    return await get_ticket(ticket_id, current_user)


@router.post("/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    assignment: TicketAssign,
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Assign ticket to an agent"""
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticket ID format"
        )
    
    db = get_database()
    
    # Verify ticket exists
    ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Verify assigned user exists and is an agent/admin
    assigned_user = await db.users.find_one({"_id": ObjectId(assignment.assigned_to)})
    if not assigned_user or assigned_user["role"] not in [UserRole.AGENT, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user assignment"
        )
    
    # Update ticket
    await db.tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$set": {
                "assigned_to": ObjectId(assignment.assigned_to),
                "status": TicketStatus.IN_PROGRESS,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Send notification to assigned user
    await notification_service.notify_ticket_assignment(
        ticket_id,
        assignment.assigned_to,
        str(current_user.id)
    )
    
    # Also send status change notification if ticket was open
    if ticket.get("status") == TicketStatus.OPEN:
        await notification_service.notify_ticket_status_change(
            ticket_id,
            TicketStatus.OPEN.value,
            TicketStatus.IN_PROGRESS.value,
            str(current_user.id)
        )
    
    return {"message": "Ticket assigned successfully"}


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(
    ticket_id: str,
    current_user: UserResponse = Depends(get_agent_or_admin_user)
):
    """Delete a ticket (admin/agent only)"""
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticket ID format"
        )
    
    db = get_database()
    
    result = await db.tickets.delete_one({"_id": ObjectId(ticket_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )


@router.get("/stats/overview", response_model=TicketStats)
async def get_ticket_stats(current_user: UserResponse = Depends(get_agent_or_admin_user)):
    """Get ticket statistics (admin/agent only)"""
    db = get_database()
    
    # Basic counts
    total_tickets = await db.tickets.count_documents({})
    open_tickets = await db.tickets.count_documents({"status": TicketStatus.OPEN})
    in_progress_tickets = await db.tickets.count_documents({"status": TicketStatus.IN_PROGRESS})
    resolved_tickets = await db.tickets.count_documents({"status": TicketStatus.RESOLVED})
    closed_tickets = await db.tickets.count_documents({"status": TicketStatus.CLOSED})
    high_priority_tickets = await db.tickets.count_documents({"priority": TicketPriority.HIGH})
    urgent_tickets = await db.tickets.count_documents({"priority": TicketPriority.URGENT})
    
    # Tickets by category
    category_pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
    ]
    category_results = await db.tickets.aggregate(category_pipeline).to_list(None)
    tickets_by_category = {result["_id"]: result["count"] for result in category_results}
    
    # Tickets by agent
    agent_pipeline = [
        {"$match": {"assigned_to": {"$ne": None}}},
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_to",
                "foreignField": "_id",
                "as": "agent"
            }
        },
        {"$unwind": "$agent"},
        {"$group": {"_id": "$agent.full_name", "count": {"$sum": 1}}}
    ]
    agent_results = await db.tickets.aggregate(agent_pipeline).to_list(None)
    tickets_by_agent = {result["_id"]: result["count"] for result in agent_results}
    
    return TicketStats(
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
        closed_tickets=closed_tickets,
        high_priority_tickets=high_priority_tickets,
        urgent_tickets=urgent_tickets,
        tickets_by_category=tickets_by_category,
        tickets_by_agent=tickets_by_agent
    ) 