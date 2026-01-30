from fastapi import APIRouter, Depends, File, UploadFile, Form, Query
from typing import Optional
from app.database import Database
from app.services.auth.profile import ProfileService
from app.routes.auth.dependencies import get_current_user
from app.models.auth.profile import ProfileUpdate, UserProfileResponse
from app.utils.response import success_response, error_response, validation_error_response
from app.utils.file_upload import FileUploadService

router = APIRouter(prefix="/api/users", tags=["User Profile"])


@router.get("/@{username}/profile")
async def get_user_profile_by_username(username: str):
    """
    Get complete user profile by username (slug).
    
    Public endpoint - shareable profile URL.
    Example: /api/users/@john_doe/profile
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Find user by username
    user = await profile_service.get_user_by_username(username)
    
    if not user:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    # Get full profile using user_id
    profile = await profile_service.get_user_profile(str(user["_id"]))
    
    if not profile:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    return success_response(
        message="Profile retrieved successfully",
        data={"profile": profile}
    )


@router.get("/{user_id}/profile")
async def get_user_profile(user_id: str):
    """
    Get complete user profile by user ID.
    
    Public endpoint - anyone can view user profiles.
    For shareable URLs, use /@{username}/profile instead.
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    profile = await profile_service.get_user_profile(user_id)
    
    if not profile:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    return success_response(
        message="Profile retrieved successfully",
        data={"profile": profile}
    )


@router.put("/profile")
async def update_own_profile(
    full_name: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    about_me: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Update current user's profile information.
    
    Requires authentication.
    Note: Username cannot be changed after registration.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # Validate inputs
    if full_name is not None and (len(full_name) < 1 or len(full_name) > 100):
        return validation_error_response(
            errors={"full_name": "Must be 1-100 characters"}
        )
    
    if title is not None and len(title) > 200:
        return validation_error_response(
            errors={"title": "Must be maximum 200 characters"}
        )
    
    if location is not None and len(location) > 100:
        return validation_error_response(
            errors={"location": "Must be maximum 100 characters"}
        )
    
    if website is not None and len(website) > 200:
        return validation_error_response(
            errors={"website": "Must be maximum 200 characters"}
        )
    
    if about_me is not None and len(about_me) > 5000:
        return validation_error_response(
            errors={"about_me": "Must be maximum 5000 characters"}
        )
    
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Create update object
    profile_update = ProfileUpdate(
        full_name=full_name,
        title=title,
        location=location,
        website=website,
        about_me=about_me
    )
    
    success, message, updated_profile = await profile_service.update_user_profile(
        user_id=str(current_user["_id"]),
        profile_data=profile_update
    )
    
    if not success:
        return error_response(message=message)
    
    return success_response(
        message=message,
        data={"profile": updated_profile}
    )


@router.post("/profile/avatar")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload/update user profile picture.
    
    Only image files allowed (jpg, png, gif, webp).
    Max size: 5MB
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        return validation_error_response(
            errors={"file": f"Only image files allowed: {', '.join(allowed_types)}"}
        )
    
    try:
        file_service = FileUploadService()
        user_id = str(current_user["_id"])
        
        # Save file
        file_info = await file_service.save_file(file, user_id)
        
        # Update user profile
        db = Database.get_db()
        profile_service = ProfileService(db)
        
        success = await profile_service.update_profile_picture(
            user_id=user_id,
            image_url=file_info["file_url"]
        )
        
        if not success:
            return error_response(message="Failed to update profile picture")
        
        return success_response(
            message="Profile picture updated successfully",
            data={"profile_picture": file_info["file_url"]},
            status_code=200
        )
        
    except ValueError as e:
        return validation_error_response(errors={"file": str(e)})
    except Exception as e:
        return error_response(message=f"Failed to upload file: {str(e)}")


@router.post("/profile/cover")
async def upload_cover_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload/update user profile cover image.
    
    Only image files allowed (jpg, png, gif, webp).
    Max size: 10MB
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        return validation_error_response(
            errors={"file": f"Only image files allowed: {', '.join(allowed_types)}"}
        )
    
    try:
        file_service = FileUploadService()
        user_id = str(current_user["_id"])
        
        # Save file
        file_info = await file_service.save_file(file, user_id)
        
        # Update user cover image
        db = Database.get_db()
        profile_service = ProfileService(db)
        
        success = await profile_service.update_cover_image(
            user_id=user_id,
            image_url=file_info["file_url"]
        )
        
        if not success:
            return error_response(message="Failed to update cover image")
        
        return success_response(
            message="Cover image updated successfully",
            data={"cover_image": file_info["file_url"]},
            status_code=200
        )
        
    except ValueError as e:
        return validation_error_response(errors={"file": str(e)})
    except Exception as e:
        return error_response(message=f"Failed to upload file: {str(e)}")


@router.get("/@{username}/questions")
async def get_user_questions_by_username(
    username: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", regex="^(created_at|upvote_count|view_count)$")
):
    """
    Get all questions posted by a user (by username).
    
    Public endpoint - sorted by date, votes, or views.
    Example: /api/users/@john_doe/questions
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Find user by username first
    user = await profile_service.get_user_by_username(username)
    if not user:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    user_id = str(user["_id"])
    
    posts, total = await profile_service.get_user_posts(
        user_id=user_id,
        page=page,
        limit=limit,
        sort_by=sort_by
    )
    
    total_pages = (total + limit - 1) // limit
    
    return success_response(
        message="Questions retrieved successfully",
        data={
            "questions": posts,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
        }
    )


@router.get("/{user_id}/questions")
async def get_user_questions(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", regex="^(created_at|upvote_count|view_count)$")
):
    """
    Get all questions posted by a user (by user ID).
    
    Public endpoint - sorted by date, votes, or views.
    For shareable URLs, use /@{username}/questions instead.
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    posts, total = await profile_service.get_user_posts(
        user_id=user_id,
        page=page,
        limit=limit,
        sort_by=sort_by
    )
    
    total_pages = (total + limit - 1) // limit
    
    return success_response(
        message="Questions retrieved successfully",
        data={
            "questions": posts,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
        }
    )


@router.get("/@{username}/answers")
async def get_user_answers_by_username(
    username: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", regex="^(created_at|upvote_count)$")
):
    """
    Get all answers posted by a user (by username).
    
    Public endpoint - includes post title and link.
    Example: /api/users/@john_doe/answers
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Find user by username first
    user = await profile_service.get_user_by_username(username)
    if not user:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    user_id = str(user["_id"])
    
    answers, total = await profile_service.get_user_answers(
        user_id=user_id,
        page=page,
        limit=limit,
        sort_by=sort_by
    )
    
    total_pages = (total + limit - 1) // limit
    
    return success_response(
        message="Answers retrieved successfully",
        data={
            "answers": answers,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
        }
    )


@router.get("/{user_id}/answers")
async def get_user_answers(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", regex="^(created_at|upvote_count)$")
):
    """
    Get all answers posted by a user (by user ID).
    
    Public endpoint - includes post title and link.
    For shareable URLs, use /@{username}/answers instead.
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    answers, total = await profile_service.get_user_answers(
        user_id=user_id,
        page=page,
        limit=limit,
        sort_by=sort_by
    )
    
    total_pages = (total + limit - 1) // limit
    
    return success_response(
        message="Answers retrieved successfully",
        data={
            "answers": answers,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
        }
    )


@router.get("/@{username}/statistics")
async def get_user_statistics_by_username(username: str):
    """
    Get user statistics by username (reputation, badges, ranks).
    
    Lightweight endpoint for displaying user stats without full profile.
    Example: /api/users/@john_doe/statistics
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Find user by username
    user = await profile_service.get_user_by_username(username)
    if not user:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    user_id = str(user["_id"])
    
    stats = await profile_service.calculate_user_statistics(user_id)
    badges = await profile_service.calculate_user_badges(user_id, stats)
    
    return success_response(
        message="Statistics retrieved successfully",
        data={
            "statistics": stats,
            "badges": badges
        }
    )


@router.get("/{user_id}/statistics")
async def get_user_statistics(user_id: str):
    """
    Get user statistics by user ID (reputation, badges, ranks).
    
    Lightweight endpoint for displaying user stats without full profile.
    For shareable URLs, use /@{username}/statistics instead.
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Check if user exists
    from app.services.auth.auth_service import AuthService
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    
    if not user:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    stats = await profile_service.calculate_user_statistics(user_id)
    badges = await profile_service.calculate_user_badges(user_id, stats)
    
    return success_response(
        message="Statistics retrieved successfully",
        data={
            "statistics": stats,
            "badges": badges
        }
    )


@router.get("/@{username}/top-tags")
async def get_user_top_tags_by_username(
    username: str,
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get user's most used tags (by username).
    
    Shows which topics the user is most active in.
    Example: /api/users/@john_doe/top-tags
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Find user by username
    user = await profile_service.get_user_by_username(username)
    if not user:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    user_id = str(user["_id"])
    top_tags = await profile_service.get_user_top_tags(user_id, limit=limit)
    
    return success_response(
        message="Top tags retrieved successfully",
        data={"top_tags": top_tags}
    )


@router.get("/{user_id}/top-tags")
async def get_user_top_tags(
    user_id: str,
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get user's most used tags (by user ID).
    
    Shows which topics the user is most active in.
    For shareable URLs, use /@{username}/top-tags instead.
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    top_tags = await profile_service.get_user_top_tags(user_id, limit=limit)
    
    return success_response(
        message="Top tags retrieved successfully",
        data={"top_tags": top_tags}
    )


@router.get("/@{username}/top-posts")
async def get_user_top_posts_by_username(
    username: str,
    limit: int = Query(4, ge=1, le=20)
):
    """
    Get user's highest voted posts (by username).
    
    Shows user's best contributions.
    Example: /api/users/@john_doe/top-posts
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    # Find user by username
    user = await profile_service.get_user_by_username(username)
    if not user:
        return error_response(
            message="User not found",
            status_code=404
        )
    
    user_id = str(user["_id"])
    top_posts = await profile_service.get_user_top_posts(user_id, limit=limit)
    
    return success_response(
        message="Top posts retrieved successfully",
        data={"top_posts": top_posts}
    )


@router.get("/{user_id}/top-posts")
async def get_user_top_posts(
    user_id: str,
    limit: int = Query(4, ge=1, le=20)
):
    """
    Get user's highest voted posts (by user ID).
    
    Shows user's best contributions.
    For shareable URLs, use /@{username}/top-posts instead.
    """
    db = Database.get_db()
    profile_service = ProfileService(db)
    
    top_posts = await profile_service.get_user_top_posts(user_id, limit=limit)
    
    return success_response(
        message="Top posts retrieved successfully",
        data={"top_posts": top_posts}
    )
