import os
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OTPBase(BaseModel):
    """Base OTP schema"""
    email: EmailStr
    otp_code: str


class OTPCreate(BaseModel):
    """Schema for OTP creation"""
    email: EmailStr


class OTPVerify(BaseModel):
    """Schema for OTP verification"""
    email: EmailStr
    otp_code: str


class OTPInDB(OTPBase):
    """Schema for OTP in database"""
    created_at: datetime
    expires_at: datetime
    is_used: bool = False
    attempts: int = 0
    
    @classmethod
    def create(cls, email: str, otp_code: str):
        """Create new OTP with expiration"""
        now = datetime.utcnow()
        otp_expire_minutes = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
        return cls(
            email=email,
            otp_code=otp_code,
            created_at=now,
            expires_at=now + timedelta(minutes=otp_expire_minutes),
            is_used=False,
            attempts=0
        )
