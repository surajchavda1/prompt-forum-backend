from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AuthProvider(str, Enum):
    """Authentication provider types"""
    EMAIL = "email"
    GOOGLE = "google"


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user creation with email/password"""
    password: str = Field(..., min_length=8, max_length=72)


class UserUpdate(BaseModel):
    """Schema for user updates (email and username cannot be changed)"""
    full_name: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response"""
    id: str = Field(..., alias="_id")
    auth_provider: AuthProvider
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "full_name": "John Doe",
                "auth_provider": "email",
                "is_verified": True,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }


class UserInDB(UserBase):
    """Schema for user in database"""
    username: Optional[str] = None
    hashed_password: Optional[str] = None
    auth_provider: AuthProvider
    google_id: Optional[str] = None
    is_verified: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
