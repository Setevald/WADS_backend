"""
User-related Pydantic models
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from bson import ObjectId


class UserRole(str, Enum):
    """User role enumeration"""
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """User status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema()
        )
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    def __str__(self):
        return str(ObjectId(self))


class UserBase(BaseModel):
    """Base user model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.CUSTOMER
    status: UserStatus = UserStatus.ACTIVE
    phone: Optional[str] = Field(None, pattern=r'^\+?[\d\s\-\(\)]{10,15}$')
    department: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = None
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must contain only alphanumeric characters, underscores, and hyphens')
        return v.lower()


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8, max_length=128)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserUpdate(BaseModel):
    """User update model"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\+?[\d\s\-\(\)]{10,15}$')
    department: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = None
    status: Optional[UserStatus] = None


class UserLogin(BaseModel):
    """User login model"""
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """User response model"""
    model_config = ConfigDict(
        populate_by_name=True, 
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        by_alias=True
    )
    
    id: PyObjectId = Field(alias="_id")
    username: str
    email: EmailStr
    full_name: str
    role: UserRole
    status: UserStatus
    phone: Optional[str] = None
    department: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class UserProfile(BaseModel):
    """User profile model for public display"""
    model_config = ConfigDict(
        populate_by_name=True, 
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        by_alias=True
    )
    
    id: PyObjectId = Field(alias="_id")
    username: str
    full_name: str
    role: UserRole
    department: Optional[str] = None
    avatar_url: Optional[str] = None


class PasswordChange(BaseModel):
    """Password change model"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class Token(BaseModel):
    """JWT token model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenData(BaseModel):
    """Token data model"""
    user_id: Optional[str] = None
    email: Optional[str] = None 