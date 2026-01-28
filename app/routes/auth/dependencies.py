from typing import Annotated
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import Database
from app.services.auth.security import SecurityService
from app.services.auth.auth_service import AuthService

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Security service
security_service = SecurityService()


async def get_database():
    """Database dependency"""
    return Database.get_db()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> dict:
    """Get current authenticated user"""
    # Verify token
    token_data = security_service.verify_token(token, "access")
    if token_data is None or token_data.email is None:
        return None
    
    # Get user from database
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_email(token_data.email)
    
    if user is None:
        return None
    
    if not user.get("is_active"):
        return None
    
    return user
