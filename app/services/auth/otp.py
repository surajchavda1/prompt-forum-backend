import os
import random
import string
from datetime import datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from dotenv import load_dotenv
from app.models.auth.otp import OTPInDB

# Load environment variables
load_dotenv()


class OTPService:
    """Service for OTP operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.otps
    
    @staticmethod
    def generate_otp() -> str:
        """Generate a random OTP code"""
        otp_length = int(os.getenv("OTP_LENGTH", "6"))
        return ''.join(random.choices(string.digits, k=otp_length))
    
    async def create_otp(self, email: str) -> str:
        """Create and store OTP for an email"""
        # Invalidate any existing OTPs for this email
        await self.collection.update_many(
            {"email": email, "is_used": False},
            {"$set": {"is_used": True}}
        )
        
        # Generate new OTP
        otp_code = self.generate_otp()
        otp_data = OTPInDB.create(email=email, otp_code=otp_code)
        
        # Store in database
        await self.collection.insert_one(otp_data.model_dump())
        
        return otp_code
    
    async def verify_otp(self, email: str, otp_code: str) -> bool:
        """Verify OTP code for an email"""
        otp = await self.collection.find_one({
            "email": email,
            "otp_code": otp_code,
            "is_used": False
        })
        
        if not otp:
            return False
        
        # Check expiration
        if datetime.utcnow() > otp["expires_at"]:
            return False
        
        # Check max attempts
        if otp["attempts"] >= 5:
            return False
        
        # Mark as used
        await self.collection.update_one(
            {"_id": otp["_id"]},
            {"$set": {"is_used": True}}
        )
        
        return True
    
    async def increment_attempts(self, email: str, otp_code: str):
        """Increment failed OTP attempts"""
        await self.collection.update_one(
            {"email": email, "otp_code": otp_code, "is_used": False},
            {"$inc": {"attempts": 1}}
        )
    
    async def cleanup_expired_otps(self):
        """Remove expired OTPs from database"""
        await self.collection.delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })
