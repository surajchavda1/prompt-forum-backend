from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from typing import List, Optional
from app.database import Database
from app.services.forum.comment import CommentService
from app.services.forum.post import PostService
from app.utils.file_upload import FileUploadService, MAX_FILES_PER_UPLOAD
from app.utils.response import success_response, error_response, validation_error_response
from app.routes.auth.dependencies import get_current_user
from datetime import datetime

router = APIRouter(prefix="/comments", tags=["Forum Comments"])


def convert_comment_to_json(comment: dict) -> dict:
    """Convert comment document to JSON-serializable format"""
    comment["id"] = str(comment["_id"])
    del comment["_id"]
    if comment.get("created_at"):
        comment["created_at"] = comment["created_at"].isoformat()
    if comment.get("updated_at"):
        comment["updated_at"] = comment["updated_at"].isoformat()
    
    # Convert attachment dates
    for attachment in comment.get("attachments", []):
        if attachment.get("uploaded_at"):
            if isinstance(attachment["uploaded_at"], datetime):
                attachment["uploaded_at"] = attachment["uploaded_at"].isoformat()
    
    # Remove voter arrays from response (privacy)
    comment.pop("upvoters", None)
    comment.pop("downvoters", None)
    
    return comment


@router.post("/{post_id}/create")
async def create_comment(
    post_id: str,
    body: str = Form(..., min_length=10),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new comment/answer on a post.
    
    Features:
    - Rich text body content
    - File attachments (images, PDFs, videos, etc.)
    - Author tracking
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    post_service = PostService(db)
    comment_service = CommentService(db)
    
    # Verify post exists
    post = await post_service.get_post_by_id(post_id)
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    # Check if post is locked
    if post.get("is_locked", False):
        return error_response(
            message="Post is locked. Cannot add comments.",
            status_code=403
        )
    
    # Handle file uploads
    attachments = []
    if files and files[0].filename:  # Check if files were actually uploaded
        if len(files) > MAX_FILES_PER_UPLOAD:
            return validation_error_response(
                errors={"files": f"Maximum {MAX_FILES_PER_UPLOAD} files allowed"}
            )
        
        file_service = FileUploadService()
        user_id = str(current_user["_id"])
        
        for uploaded_file in files:
            try:
                # Validate and save file
                file_info = await file_service.save_file(uploaded_file, user_id)
                attachments.append(file_info)
            except ValueError as e:
                # Clean up already uploaded files
                for att in attachments:
                    await file_service.delete_file(att["filename"], user_id)
                return validation_error_response(
                    errors={"files": str(e)}
                )
    
    try:
        # Create comment (answer to post)
        comment = await comment_service.create_comment(
            post_id=post_id,
            author_id=str(current_user["_id"]),
            author_name=current_user.get("full_name") or current_user.get("email"),
            body=body,
            attachments=attachments,
            is_post_comment=False  # This is an ANSWER, not a comment on question
        )
        
        # Increment post reply count
        await post_service.increment_reply_count(post_id)
        
        # Convert to JSON
        comment_data = convert_comment_to_json(comment)
        
        return success_response(
            message="Comment created successfully",
            data={"comment": comment_data},
            status_code=201
        )
        
    except Exception as e:
        # Clean up uploaded files on error
        file_service = FileUploadService()
        user_id = str(current_user["_id"])
        for att in attachments:
            await file_service.delete_file(att["filename"], user_id)
        
        return error_response(
            message=f"Failed to create comment: {str(e)}"
        )


@router.get("/{post_id}/all")
async def get_comments(
    post_id: str,
    sort_by: str = Query("created_at", pattern="^(created_at|upvote_count)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get all comments for a post.
    
    Sorting options:
    - created_at (asc/desc) - Oldest/Newest first
    - upvote_count (desc) - Highest score first (like Stack Overflow)
    """
    db = Database.get_db()
    comment_service = CommentService(db)
    post_service = PostService(db)
    
    # Verify post exists
    post = await post_service.get_post_by_id(post_id)
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    # Get comments
    comments = await comment_service.get_comments_by_post(
        post_id=post_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit
    )
    
    # Get total count
    total = await comment_service.count_comments(post_id)
    
    # Convert comments to JSON
    comments_data = [convert_comment_to_json(comment) for comment in comments]
    
    # Separate accepted solution
    accepted_solution = None
    other_comments = []
    
    for comment in comments_data:
        if comment.get("is_accepted"):
            accepted_solution = comment
        else:
            other_comments.append(comment)
    
    return success_response(
        message="Comments retrieved successfully",
        data={
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
            "accepted_solution": accepted_solution,
            "comments": other_comments
        }
    )


@router.post("/{comment_id}/update")
async def update_comment(
    comment_id: str,
    body: Optional[str] = Form(None, min_length=10),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a comment.
    Only the comment author can update.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    comment_service = CommentService(db)
    
    # Get comment
    comment = await comment_service.get_comment_by_id(comment_id)
    if not comment:
        return error_response(
            message="Comment not found",
            status_code=404
        )
    
    # Check ownership
    if comment["author_id"] != str(current_user["_id"]):
        return error_response(
            message="You can only edit your own comments",
            status_code=403
        )
    
    # Handle new file uploads if provided
    attachments = None
    if files and files[0].filename:
        if len(files) > MAX_FILES_PER_UPLOAD:
            return validation_error_response(
                errors={"files": f"Maximum {MAX_FILES_PER_UPLOAD} files allowed"}
            )
        
        file_service = FileUploadService()
        user_id = str(current_user["_id"])
        attachments = []
        
        for uploaded_file in files:
            try:
                file_info = await file_service.save_file(uploaded_file, user_id)
                attachments.append(file_info)
            except ValueError as e:
                # Clean up
                for att in attachments:
                    await file_service.delete_file(att["filename"], user_id)
                return validation_error_response(
                    errors={"files": str(e)}
                )
    
    # Update comment
    success = await comment_service.update_comment(
        comment_id=comment_id,
        body=body,
        attachments=attachments
    )
    
    if not success:
        return error_response(message="Failed to update comment")
    
    # Get updated comment
    updated_comment = await comment_service.get_comment_by_id(comment_id)
    comment_data = convert_comment_to_json(updated_comment)
    
    return success_response(
        message="Comment updated successfully",
        data={"comment": comment_data}
    )


@router.post("/{comment_id}/delete")
async def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a comment.
    Only the comment author can delete.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    comment_service = CommentService(db)
    
    # Get comment
    comment = await comment_service.get_comment_by_id(comment_id)
    if not comment:
        return error_response(
            message="Comment not found",
            status_code=404
        )
    
    # Check ownership
    if comment["author_id"] != str(current_user["_id"]):
        return error_response(
            message="You can only delete your own comments",
            status_code=403
        )
    
    # Delete comment
    success = await comment_service.delete_comment(comment_id)
    
    if not success:
        return error_response(message="Failed to delete comment")
    
    return success_response(
        message="Comment deleted successfully",
        data={"comment_id": comment_id}
    )


@router.post("/{comment_id}/vote")
async def vote_on_comment(
    comment_id: str,
    vote_type: str = Form(..., pattern="^(upvote|downvote)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Vote on a comment (upvote or downvote).
    Users can:
    - Upvote or downvote a comment
    - Remove their vote by clicking the same button
    - Change their vote from upvote to downvote or vice versa
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    comment_service = CommentService(db)
    
    # Verify comment exists
    comment = await comment_service.get_comment_by_id(comment_id)
    if not comment:
        return error_response(
            message="Comment not found",
            status_code=404
        )
    
    # Pass user_id to track votes
    user_id = str(current_user["_id"])
    success, message, vote_info = await comment_service.vote_comment(comment_id, user_id, vote_type)
    
    if not success:
        return error_response(message=message)
    
    return success_response(
        message=message,
        data={
            "comment_id": comment_id,
            "vote_info": vote_info
        }
    )


@router.post("/{comment_id}/accept")
async def accept_comment_as_solution(
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a comment as the accepted solution.
    Only the post author can accept solutions.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    comment_service = CommentService(db)
    post_service = PostService(db)
    
    # Get comment
    comment = await comment_service.get_comment_by_id(comment_id)
    if not comment:
        return error_response(
            message="Comment not found",
            status_code=404
        )
    
    # Get post to check ownership
    post = await post_service.get_post_by_id(comment["post_id"])
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    # Check if current user is the post author
    if post["author_id"] != str(current_user["_id"]):
        return error_response(
            message="Only the post author can accept solutions",
            status_code=403
        )
    
    # Accept the comment
    success = await comment_service.accept_comment(comment_id, comment["post_id"])
    
    if not success:
        return error_response(message="Failed to accept comment")
    
    # Mark post as solved
    await post_service.mark_solved(comment["post_id"])
    
    return success_response(
        message="Comment accepted as solution",
        data={"comment_id": comment_id}
    )


@router.post("/{comment_id}/unaccept")
async def unaccept_comment_solution(
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove accepted solution status from a comment.
    Only the post author can unaccept solutions.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    comment_service = CommentService(db)
    post_service = PostService(db)
    
    # Get comment
    comment = await comment_service.get_comment_by_id(comment_id)
    if not comment:
        return error_response(
            message="Comment not found",
            status_code=404
        )
    
    # Get post to check ownership
    post = await post_service.get_post_by_id(comment["post_id"])
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    # Check if current user is the post author
    if post["author_id"] != str(current_user["_id"]):
        return error_response(
            message="Only the post author can unaccept solutions",
            status_code=403
        )
    
    # Unaccept the comment
    success = await comment_service.unaccept_comment(comment_id)
    
    if not success:
        return error_response(message="Failed to unaccept comment")
    
    return success_response(
        message="Comment unaccepted",
        data={"comment_id": comment_id}
    )


@router.post("/{comment_id}/reply")
async def reply_to_comment(
    comment_id: str,
    body: str = Form(..., min_length=10),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user)
):
    """
    Reply to a comment (create nested comment).
    Creates a sub-comment that references the parent comment.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    comment_service = CommentService(db)
    
    # Verify parent comment exists
    parent_comment = await comment_service.get_comment_by_id(comment_id)
    if not parent_comment:
        return error_response(
            message="Parent comment not found",
            status_code=404
        )
    
    # Handle file uploads
    attachments = []
    if files and files[0].filename:
        if len(files) > MAX_FILES_PER_UPLOAD:
            return validation_error_response(
                errors={"files": f"Maximum {MAX_FILES_PER_UPLOAD} files allowed"}
            )
        
        file_service = FileUploadService()
        user_id = str(current_user["_id"])
        
        for uploaded_file in files:
            try:
                file_info = await file_service.save_file(uploaded_file, user_id)
                attachments.append(file_info)
            except ValueError as e:
                # Clean up already uploaded files
                for att in attachments:
                    await file_service.delete_file(att["filename"], user_id)
                return validation_error_response(
                    errors={"files": str(e)}
                )
    
    try:
        # Create reply with parent_id (nested comment on answer)
        reply = await comment_service.create_comment(
            post_id=parent_comment["post_id"],  # Same post as parent
            parent_id=comment_id,  # Reference to parent comment
            author_id=str(current_user["_id"]),
            author_name=current_user.get("full_name") or current_user.get("email"),
            body=body,
            attachments=attachments,
            is_post_comment=False  # This is a reply to answer, not question comment
        )
        
        # Convert to JSON
        reply_data = convert_comment_to_json(reply)
        
        return success_response(
            message="Reply posted successfully",
            data={"reply": reply_data},
            status_code=201
        )
        
    except Exception as e:
        return error_response(
            message=f"Failed to post reply: {str(e)}",
            status_code=500
        )


@router.get("/{comment_id}/replies")
async def get_comment_replies(
    comment_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get all replies to a specific comment.
    Returns nested comments for threading display.
    """
    db = Database.get_db()
    comment_service = CommentService(db)
    
    # Verify parent comment exists
    parent_comment = await comment_service.get_comment_by_id(comment_id)
    if not parent_comment:
        return error_response(
            message="Comment not found",
            status_code=404
        )
    
    skip = (page - 1) * limit
    replies = await comment_service.get_replies(comment_id, skip, limit)
    total_replies = await comment_service.count_replies(comment_id)
    
    # Convert all replies to JSON
    replies_data = [convert_comment_to_json(reply) for reply in replies]
    
    return success_response(
        message="Replies retrieved successfully",
        data={
            "parent_comment_id": comment_id,
            "replies": replies_data,
            "pagination": {
                "total": total_replies,
                "page": page,
                "limit": limit,
                "total_pages": (total_replies + limit - 1) // limit
            }
        }
    )
