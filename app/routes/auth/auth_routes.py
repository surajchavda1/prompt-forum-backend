from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.models.auth.user import UserResponse
from app.models.auth.token import (
    Token,
    EmailPasswordLogin,
    EmailSignup,
    GoogleAuthRequest,
    RefreshTokenRequest,
    PasswordReset
)
from app.models.auth.otp import OTPVerify, OTPCreate
from app.services.auth.auth_service import AuthService
from app.services.auth.security import security_service
from app.routes.auth.dependencies import get_current_user
from app.utils.response import (
    success_response,
    error_response,
    validation_error_response,
    unauthorized_response
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup")
async def signup(
    signup_data: EmailSignup,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Sign up new user with email and password.
    Sends OTP to email for verification.
    """
    try:
        auth_service = AuthService(db)
        user = await auth_service.signup_with_email(signup_data)
        
        return success_response(
            message="User created successfully. Please check your email for verification code.",
            data={"email": signup_data.email}
        )
    except ValueError as e:
        return error_response(message=str(e))
    except Exception as e:
        # Log the actual error for debugging
        print(f"❌ Signup error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(message=f"Failed to create user: {str(e)}")


@router.post("/verify-email")
async def verify_email(
    verify_data: OTPVerify,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Verify email with OTP code.
    Returns access and refresh tokens on success.
    """
    try:
        auth_service = AuthService(db)
        
        # Check if user exists first
        user = await auth_service.get_user_by_email(verify_data.email)
        if not user:
            return error_response(message="User not found")
        
        # Verify OTP
        is_verified = await auth_service.verify_email(verify_data.email, verify_data.otp_code)
        
        if not is_verified:
            return error_response(message="Invalid or expired OTP code")
        
        # Get updated user and generate tokens
        user = await auth_service.get_user_by_email(verify_data.email)
        if not user:
            return error_response(message="User not found")
        
        access_token = security_service.create_access_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        refresh_token = security_service.create_refresh_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        
        return success_response(
            message="Email verified successfully",
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }
        )
    except ValueError as e:
        # SECRET_KEY related errors
        if "SECRET_KEY" in str(e):
            print(f"❌ Configuration error: {str(e)}")
            return error_response(
                message="Server configuration error. Please contact administrator."
            )
        return error_response(message=str(e))
    except Exception as e:
        # Log the actual error for debugging
        print(f"❌ Verification error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(message="Verification failed")


@router.post("/login")
async def login(
    login_data: EmailPasswordLogin,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Login with email and password.
    Returns access and refresh tokens on success.
    """
    try:
        auth_service = AuthService(db)
        user = await auth_service.login_with_email(login_data)
        
        if not user:
            return unauthorized_response(message="Incorrect email or password")
        
        # Generate tokens
        access_token = security_service.create_access_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        refresh_token = security_service.create_refresh_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        
        return success_response(
            message="Login successful",
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }
        )
    except ValueError as e:
        return error_response(message=str(e))
    except Exception as e:
        return error_response(message="Login failed")


@router.post("/google")
async def google_auth(
    google_data: GoogleAuthRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Authenticate with Google OAuth.
    Creates new user if doesn't exist.
    Returns access and refresh tokens on success.
    """
    try:
        auth_service = AuthService(db)
        user = await auth_service.login_with_google(google_data.token)
        
        # Generate tokens
        access_token = security_service.create_access_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        refresh_token = security_service.create_refresh_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        
        return success_response(
            message="Google authentication successful",
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }
        )
    except ValueError as e:
        return error_response(message=str(e))
    except Exception as e:
        return error_response(message="Google authentication failed")


@router.post("/refresh")
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Refresh access token using refresh token.
    Returns new access and refresh tokens.
    """
    try:
        # Verify refresh token
        token_data = security_service.verify_token(refresh_data.refresh_token, "refresh")
        
        if token_data is None or token_data.email is None:
            return unauthorized_response(message="Invalid refresh token")
        
        # Get user
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_email(token_data.email)
        
        if not user:
            return unauthorized_response(message="User not found")
        
        # Generate new tokens
        access_token = security_service.create_access_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        refresh_token = security_service.create_refresh_token(
            data={"sub": user["email"], "user_id": str(user["_id"])}
        )
        
        return success_response(
            message="Token refreshed successfully",
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }
        )
    except Exception as e:
        return error_response(message="Token refresh failed")


@router.post("/forgot-password")
async def forgot_password(
    request_data: OTPCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Request password reset.
    Sends OTP to email if user exists.
    """
    try:
        auth_service = AuthService(db)
        await auth_service.request_password_reset(request_data.email)
        
        return success_response(
            message="If the email exists, a password reset code has been sent."
        )
    except ValueError as e:
        return error_response(message=str(e))
    except Exception as e:
        return error_response(message="Failed to process request")


@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordReset,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Reset password using OTP code.
    """
    try:
        auth_service = AuthService(db)
        is_reset = await auth_service.reset_password(
            reset_data.email,
            reset_data.otp_code,
            reset_data.new_password
        )
        
        if not is_reset:
            return error_response(message="Invalid or expired OTP code")
        
        return success_response(message="Password reset successfully")
    except Exception as e:
        return error_response(message="Password reset failed")


@router.post("/resend-otp")
async def resend_otp(
    request_data: OTPCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Resend OTP code to email.
    """
    try:
        auth_service = AuthService(db)
        is_sent = await auth_service.resend_otp(request_data.email)
        
        if not is_sent:
            return error_response(message="User not found")
        
        return success_response(message="OTP code has been resent to your email")
    except Exception as e:
        return error_response(message="Failed to resend OTP")


@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    """
    if not current_user:
        return unauthorized_response(message="Authentication required")
    
    # Convert ObjectId and datetime to strings for JSON serialization
    user_data = {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "username": current_user.get("username"),
        "full_name": current_user.get("full_name"),
        "profile_picture": current_user.get("profile_picture"),
        "auth_provider": current_user.get("auth_provider"),
        "is_verified": current_user.get("is_verified"),
        "is_active": current_user.get("is_active"),
        "created_at": current_user.get("created_at").isoformat() if current_user.get("created_at") else None,
        "updated_at": current_user.get("updated_at").isoformat() if current_user.get("updated_at") else None
    }
    
    return success_response(
        message="User info retrieved successfully",
        data={"user": user_data}
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout current user.
    Note: In a stateless JWT system, the client should delete the token.
    For more security, implement token blacklisting.
    """
    if not current_user:
        return unauthorized_response(message="Authentication required")
    
    return success_response(message="Logged out successfully")
