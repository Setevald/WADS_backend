"""
Configuration module for the Help Desk System
Handles environment variables and application settings
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database settings
    mongodb_url: str = Field(..., description="MongoDB connection URL")
    database_name: str = Field(..., description="Database name")
    
    # JWT settings
    secret_key: str = Field(..., description="JWT secret key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Token expiration time")
    
    # Redis settings (for real-time features)
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    
    # Email settings
    smtp_server: str = Field(default="smtp.gmail.com", description="SMTP server")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    
    # Application settings
    debug: bool = Field(default=False, description="Debug mode")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"], 
        description="CORS allowed origins"
    )
    
    # File upload settings
    max_file_size: int = Field(default=5242880, description="Maximum file size in bytes")  # 5MB
    upload_dir: str = Field(default="uploads", description="Upload directory")
    allowed_file_types: List[str] = Field(
        default=[
            "image/jpeg", "image/png", "image/gif",
            "application/pdf", "text/plain",
            "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ],
        description="Allowed file types"
    )
    
    # Pagination settings
    default_page_size: int = Field(default=20, description="Default pagination size")
    max_page_size: int = Field(default=100, description="Maximum pagination size")
    
    # Security settings
    password_min_length: int = Field(default=8, description="Minimum password length")
    max_login_attempts: int = Field(default=5, description="Maximum login attempts")
    lockout_duration_minutes: int = Field(default=30, description="Lockout duration in minutes")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create settings instance
settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True) 