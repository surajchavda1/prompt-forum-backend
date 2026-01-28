from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data"""
    email: Optional[str] = None
    user_id: Optional[str] = None


class EmailPasswordLogin(BaseModel):
    """Schema for email/password login"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72, description="Password must be 8-72 characters")


class EmailSignup(BaseModel):
    """Schema for email signup"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72, description="Password must be 8-72 characters")
    full_name: Optional[str] = Field(None, max_length=100, description="Full name (optional)")


class GoogleAuthRequest(BaseModel):
    """Schema for Google authentication"""
    token: str


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str


class PasswordReset(BaseModel):
    """Schema for password reset"""
    email: EmailStr
    otp_code: str
    new_password: str = Field(..., min_length=8, max_length=72)
