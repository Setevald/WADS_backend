"""
Authentication utilities for JWT tokens and password security
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Union
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from bson import ObjectId

from app.config import settings
from app.database.connection import get_database
from app.models.user import TokenData, UserResponse, UserRole

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token security
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        token_data = TokenData(user_id=user_id, email=email)
        return token_data
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    """Get the current authenticated user"""
    token = credentials.credentials
    token_data = verify_token(token)
    
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(token_data.user_id)})
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login time
    await db.users.update_one(
        {"_id": ObjectId(token_data.user_id)},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    return UserResponse(**user)


async def get_current_active_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Get the current active user (not suspended)"""
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )
    return current_user


def require_role(required_roles: Union[UserRole, list[UserRole]]):
    """Decorator to require specific user roles"""
    if isinstance(required_roles, UserRole):
        required_roles = [required_roles]
    
    def role_checker(current_user: UserResponse = Depends(get_current_active_user)) -> UserResponse:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return role_checker


async def get_admin_user(current_user: UserResponse = Depends(require_role(UserRole.ADMIN))) -> UserResponse:
    """Get current user with admin role"""
    return current_user


async def get_agent_or_admin_user(current_user: UserResponse = Depends(require_role([UserRole.AGENT, UserRole.ADMIN]))) -> UserResponse:
    """Get current user with agent or admin role"""
    return current_user


def generate_secure_filename(filename: str) -> str:
    """Generate a secure filename with random prefix"""
    secure_random = secrets.token_hex(16)
    file_extension = filename.split('.')[-1] if '.' in filename else ''
    return f"{secure_random}.{file_extension}" if file_extension else secure_random


def validate_file_size(file_size: int) -> bool:
    """Validate file size against maximum allowed size"""
    return file_size <= settings.max_file_size


def validate_file_type(content_type: str) -> bool:
    """Validate file type against allowed types"""
    return content_type in settings.allowed_file_types


async def check_ticket_permissions(ticket_id: str, current_user: UserResponse) -> bool:
    """Check if user has permission to access a ticket"""
    db = get_database()
    ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    
    if not ticket:
        return False
    
    # Admin and agents can access all tickets
    if current_user.role in [UserRole.ADMIN, UserRole.AGENT]:
        return True
    
    # Customers can only access their own tickets
    if current_user.role == UserRole.CUSTOMER:
        return str(ticket.get("created_by")) == str(current_user.id)
    
    return False 