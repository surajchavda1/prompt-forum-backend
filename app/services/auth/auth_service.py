from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict
from datetime import datetime
from bson import ObjectId
from app.models.auth.user import (
    UserCreate,
    UserInDB,
    UserResponse,
    AuthProvider
)
from app.models.auth.token import (
    EmailSignup,
    EmailPasswordLogin
)
from app.services.auth.security import security_service
from app.services.auth.otp import OTPService
from app.services.auth.email import email_service
from app.services.auth.google_auth import google_auth_service


class AuthService:
    """Service for authentication operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users_collection = db.users
        self.otp_service = OTPService(db)
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        return await self.users_collection.find_one({"email": email})
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        try:
            return await self.users_collection.find_one({"_id": ObjectId(user_id)})
        except:
            return None
    
    async def create_user(
        self,
        email: str,
        full_name: Optional[str] = None,
        password: Optional[str] = None,
        auth_provider: AuthProvider = AuthProvider.EMAIL,
        google_id: Optional[str] = None,
        is_verified: bool = False
    ) -> Dict:
        """Create a new user"""
        user_data = UserInDB(
            email=email,
            full_name=full_name,
            hashed_password=security_service.get_password_hash(password) if password else None,
            auth_provider=auth_provider,
            google_id=google_id,
            is_verified=is_verified,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.users_collection.insert_one(user_data.model_dump())
        user = await self.users_collection.find_one({"_id": result.inserted_id})
        return user
    
    async def signup_with_email(self, signup_data: EmailSignup) -> Dict:
        """Sign up new user with email and password"""
        # Check if user already exists
        existing_user = await self.get_user_by_email(signup_data.email)
        if existing_user:
            raise ValueError("Email already registered")
        
        # Create user
        user = await self.create_user(
            email=signup_data.email,
            full_name=signup_data.full_name,
            password=signup_data.password,
            auth_provider=AuthProvider.EMAIL,
            is_verified=False
        )
        
        # Generate and send OTP
        otp_code = await self.otp_service.create_otp(signup_data.email)
        await email_service.send_otp_email(signup_data.email, otp_code)
        
        return user
    
    async def verify_email(self, email: str, otp_code: str) -> bool:
        """Verify user email with OTP"""
        # Verify OTP
        is_valid = await self.otp_service.verify_otp(email, otp_code)
        if not is_valid:
            return False
        
        # Update user as verified
        result = await self.users_collection.update_one(
            {"email": email},
            {"$set": {"is_verified": True, "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count > 0:
            # Send welcome email
            user = await self.get_user_by_email(email)
            await email_service.send_welcome_email(email, user.get("full_name"))
            return True
        
        return False
    
    async def login_with_email(self, login_data: EmailPasswordLogin) -> Optional[Dict]:
        """Login user with email and password"""
        # Get user
        user = await self.get_user_by_email(login_data.email)
        if not user:
            return None
        
        # Check auth provider
        if user.get("auth_provider") != AuthProvider.EMAIL.value:
            raise ValueError(f"Please use {user.get('auth_provider')} to login")
        
        # Verify password
        if not security_service.verify_password(login_data.password, user.get("hashed_password")):
            return None
        
        # Check if verified
        if not user.get("is_verified"):
            raise ValueError("Email not verified. Please verify your email first.")
        
        return user
    
    async def login_with_google(self, google_token: str) -> Dict:
        """Login or create user with Google OAuth"""
        # Verify Google token
        google_user_info = await google_auth_service.verify_google_token(google_token)
        if not google_user_info:
            raise ValueError("Invalid Google token")
        
        # Check if user exists
        user = await self.get_user_by_email(google_user_info["email"])
        
        if user:
            # User exists - check if it's a Google account
            if user.get("auth_provider") != AuthProvider.GOOGLE.value:
                raise ValueError(f"Email already registered with {user.get('auth_provider')}")
            
            # Update user info
            await self.users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"updated_at": datetime.utcnow()}}
            )
        else:
            # Create new user with Google
            user = await self.create_user(
                email=google_user_info["email"],
                full_name=google_user_info.get("full_name"),
                auth_provider=AuthProvider.GOOGLE,
                google_id=google_user_info["google_id"],
                is_verified=google_user_info.get("email_verified", True)
            )
            
            # Send welcome email
            await email_service.send_welcome_email(
                google_user_info["email"],
                google_user_info.get("full_name")
            )
        
        return user
    
    async def request_password_reset(self, email: str) -> bool:
        """Request password reset - send OTP"""
        # Check if user exists
        user = await self.get_user_by_email(email)
        if not user:
            # Don't reveal if user exists
            return True
        
        # Check auth provider
        if user.get("auth_provider") != AuthProvider.EMAIL.value:
            raise ValueError("Password reset not available for this account")
        
        # Generate and send OTP
        otp_code = await self.otp_service.create_otp(email)
        await email_service.send_password_reset_email(email, otp_code)
        
        return True
    
    async def reset_password(self, email: str, otp_code: str, new_password: str) -> bool:
        """Reset user password with OTP"""
        # Verify OTP
        is_valid = await self.otp_service.verify_otp(email, otp_code)
        if not is_valid:
            return False
        
        # Update password
        hashed_password = security_service.get_password_hash(new_password)
        result = await self.users_collection.update_one(
            {"email": email},
            {"$set": {
                "hashed_password": hashed_password,
                "updated_at": datetime.utcnow()
            }}
        )
        
        return result.modified_count > 0
    
    async def resend_otp(self, email: str) -> bool:
        """Resend OTP to user email"""
        # Check if user exists
        user = await self.get_user_by_email(email)
        if not user:
            return False
        
        # Generate and send new OTP
        otp_code = await self.otp_service.create_otp(email)
        await email_service.send_otp_email(email, otp_code)
        
        return True
