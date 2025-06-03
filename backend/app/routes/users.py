"""
User management routes
"""

from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId

from app.database.connection import get_database
from app.models.user import UserResponse, UserProfile, UserRole
from app.utils.auth import get_current_active_user, get_agent_or_admin_user

router = APIRouter()


@router.get("/agents", response_model=List[UserProfile])
async def get_agents(current_user: UserResponse = Depends(get_current_active_user)):
    """Get list of all agents and admins"""
    db = get_database()
    
    agents_cursor = db.users.find({
        "role": {"$in": [UserRole.AGENT, UserRole.ADMIN]},
        "status": "active"
    })
    
    agents = []
    async for user in agents_cursor:
        agents.append(UserProfile(**user))
    
    return agents


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get user profile by ID"""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserProfile(**user) 