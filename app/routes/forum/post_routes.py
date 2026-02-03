from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from typing import List, Optional
from app.database import Database
from app.services.forum.post import PostService
from app.services.forum.tag import TagService
from app.services.forum.category import CategoryService
from app.models.forum.post import PostCreate, PostUpdate
from app.utils.file_upload import FileUploadService, MAX_FILES_PER_UPLOAD
from app.utils.response import success_response, error_response, validation_error_response
from app.routes.auth.dependencies import get_current_user
from datetime import datetime

router = APIRouter(prefix="/posts", tags=["Forum Posts"])


def convert_post_to_json(post: dict) -> dict:
    """Convert post document to JSON-serializable format"""
    post["id"] = str(post["_id"])
    del post["_id"]
    if post.get("created_at"):
        post["created_at"] = post["created_at"].isoformat()
    if post.get("updated_at"):
        post["updated_at"] = post["updated_at"].isoformat()
    
    # Convert attachment dates
    for attachment in post.get("attachments", []):
        if attachment.get("uploaded_at"):
            if isinstance(attachment["uploaded_at"], datetime):
                attachment["uploaded_at"] = attachment["uploaded_at"].isoformat()
    
    return post


@router.post("/create")
async def create_post(
    title: str = Form(..., min_length=5, max_length=200),
    category_id: str = Form(...),
    subcategory_id: Optional[str] = Form(None),
    tags: str = Form("", description="Comma-separated tags"),
    body: str = Form(..., min_length=20),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new forum post/question.
    
    - **title**: Post title (5-200 characters)
    - **category_id**: Parent category ID
    - **subcategory_id**: Subcategory ID (optional)
    - **tags**: Comma-separated tag names (optional)
    - **body**: Post content (min 20 characters)
    - **files**: File attachments (optional, max 5 files)
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    post_service = PostService(db)
    category_service = CategoryService(db)
    tag_service = TagService(db)
    
    # Validate category exists and is a parent category (not a subcategory)
    category = await category_service.get_category_by_id(category_id)
    if not category:
        return validation_error_response(
            message="Invalid category",
            errors={"category_id": "Category not found"}
        )
    
    # Ensure the main category is not a subcategory
    if category.get("parent_id"):
        return validation_error_response(
            message="Invalid category",
            errors={"category_id": "Cannot use a subcategory as the main category"}
        )
    
    # Validate subcategory if provided
    if subcategory_id:
        subcategory = await category_service.get_category_by_id(subcategory_id)
        if not subcategory:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory not found"}
            )
        # Ensure subcategory belongs to the specified parent category
        if subcategory.get("parent_id") != category_id:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory doesn't belong to the selected category"}
            )
    
    # Process tags
    tag_list = []
    if tags.strip():
        tag_names = [t.strip().lower() for t in tags.split(',') if t.strip()]
        tag_names = list(set(tag_names))[:10]  # Max 10 unique tags
        
        for tag_name in tag_names:
            # Check if tag exists
            existing_tag = await tag_service.get_tag_by_slug(tag_name)
            if existing_tag:
                # Increment usage count
                await tag_service.increment_usage_count(str(existing_tag["_id"]))
                tag_list.append(tag_name)
            else:
                # Create new tag with "Community" group
                new_tag = await tag_service.create_tag(
                    name=tag_name,
                    slug=tag_name,
                    description=f"User-created tag: {tag_name}",
                    group="Community",
                    color="#06B6D4"
                )
                # Increment usage count for newly created tag
                await tag_service.increment_usage_count(str(new_tag["_id"]))
                tag_list.append(tag_name)
    
    # Handle file uploads
    attachments = []
    if files and len(files) > 0:
        # Check file count
        if len(files) > MAX_FILES_PER_UPLOAD:
            return validation_error_response(
                message=f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} files allowed",
                errors={"files": f"Maximum {MAX_FILES_PER_UPLOAD} files per post"}
            )
        
        user_id = str(current_user["_id"])
        for file in files:
            if file.filename:  # Skip empty file fields
                try:
                    file_info = await FileUploadService.save_file(file, user_id)
                    attachments.append(file_info)
                except Exception as e:
                    return error_response(
                        message=f"File upload failed: {str(e)}",
                        status_code=400
                    )
    
    # Create post
    try:
        post = await post_service.create_post(
            title=title,
            category_id=category_id,
            subcategory_id=subcategory_id,
            tags=tag_list,
            body=body,
            author_id=str(current_user["_id"]),
            author_name=current_user.get("full_name") or current_user.get("email"),
            attachments=attachments
        )
        
        # Increment category post count
        await category_service.increment_post_count(category_id)
        if subcategory_id:
            await category_service.increment_post_count(subcategory_id)
        
        # Convert to JSON
        convert_post_to_json(post)
        
        return success_response(
            message="Post created successfully",
            data={"post": post}
        )
    except Exception as e:
        return error_response(
            message=f"Failed to create post: {str(e)}"
        )


@router.get("/all")
async def get_all_posts(
    category_id: Optional[str] = Query(None, description="Category ID or slug"),
    subcategory_id: Optional[str] = Query(None, description="Subcategory ID or slug"),
    tag: Optional[str] = Query(None),
    author_id: Optional[str] = Query(None),
    is_solved: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|upvote_count|reply_count|view_count)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$")
):
    """
    Get all posts with filters and pagination.
    
    - **category_id**: Filter by category (accepts ID or slug)
    - **subcategory_id**: Filter by subcategory (accepts ID or slug)
    - **tag**: Filter by tag
    - **author_id**: Filter by author
    - **is_solved**: Filter by solved status
    - **page**: Page number (default: 1)
    - **limit**: Posts per page (default: 20, max: 100)
    - **sort_by**: Sort field (created_at, updated_at, upvote_count, reply_count, view_count)
    - **sort_order**: Sort order (asc/desc)
    """
    db = Database.get_db()
    post_service = PostService(db)
    category_service = CategoryService(db)
    
    # Resolve category_id (accept both ID and slug)
    # Smart detection: if it's a subcategory, search in subcategory_id instead
    resolved_category_id = None
    resolved_subcategory_id = None
    
    if category_id:
        is_object_id = len(category_id) == 24 and all(c in '0123456789abcdef' for c in category_id.lower())
        if is_object_id:
            # Check if this ID is a subcategory
            cat = await category_service.get_category_by_id(category_id)
            if cat and cat.get("parent_id"):
                # It's a subcategory, search in subcategory_id
                resolved_subcategory_id = category_id
            else:
                resolved_category_id = category_id
        else:
            # Look up by slug
            category = await category_service.get_category_by_slug(category_id)
            if category:
                cat_id = str(category["_id"])
                if category.get("parent_id"):
                    # It's a subcategory, search in subcategory_id
                    resolved_subcategory_id = cat_id
                else:
                    resolved_category_id = cat_id
    
    # Handle explicit subcategory_id parameter (accept both ID and slug)
    if subcategory_id:
        is_object_id = len(subcategory_id) == 24 and all(c in '0123456789abcdef' for c in subcategory_id.lower())
        if is_object_id:
            resolved_subcategory_id = subcategory_id
        else:
            # Look up by slug
            subcategory = await category_service.get_category_by_slug(subcategory_id)
            if subcategory:
                resolved_subcategory_id = str(subcategory["_id"])
    
    skip = (page - 1) * limit
    sort_dir = -1 if sort_order == "desc" else 1
    
    posts = await post_service.get_posts(
        category_id=resolved_category_id,
        subcategory_id=resolved_subcategory_id,
        tag=tag,
        author_id=author_id,
        is_solved=is_solved,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_dir
    )
    
    total = await post_service.count_posts(
        category_id=resolved_category_id,
        subcategory_id=resolved_subcategory_id,
        tag=tag,
        author_id=author_id
    )
    
    # Convert to JSON
    for post in posts:
        convert_post_to_json(post)
    
    return success_response(
        message="Posts retrieved successfully",
        data={
            "posts": posts,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/filter/active")
async def get_active_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get recently active posts (sorted by recent activity - updates, replies).
    Similar to Stack Overflow's "Active" filter.
    """
    db = Database.get_db()
    post_service = PostService(db)
    
    skip = (page - 1) * limit
    posts = await post_service.get_active_posts(skip, limit)
    total = await post_service.count_posts()
    
    # Convert to JSON
    for post in posts:
        convert_post_to_json(post)
    
    return success_response(
        message="Active posts retrieved successfully",
        data={
            "posts": posts,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/filter/unanswered")
async def get_unanswered_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get unanswered posts (posts with no replies).
    """
    db = Database.get_db()
    post_service = PostService(db)
    
    skip = (page - 1) * limit
    posts = await post_service.get_unanswered_posts(skip, limit)
    total = await post_service.count_unanswered_posts()
    
    # Convert to JSON
    for post in posts:
        convert_post_to_json(post)
    
    return success_response(
        message="Unanswered posts retrieved successfully",
        data={
            "posts": posts,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/filter/answered")
async def get_answered_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get answered posts (posts with at least one reply).
    """
    db = Database.get_db()
    post_service = PostService(db)
    
    skip = (page - 1) * limit
    posts = await post_service.get_answered_posts(skip, limit)
    total = await post_service.count_answered_posts()
    
    # Convert to JSON
    for post in posts:
        convert_post_to_json(post)
    
    return success_response(
        message="Answered posts retrieved successfully",
        data={
            "posts": posts,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/filter/trending")
async def get_trending_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get trending posts (high activity in last 7 days).
    Based on combination of views, upvotes, and replies.
    """
    db = Database.get_db()
    post_service = PostService(db)
    
    skip = (page - 1) * limit
    posts = await post_service.get_trending_posts(skip, limit)
    total = await post_service.count_trending_posts()
    
    # Convert to JSON
    for post in posts:
        convert_post_to_json(post)
    
    return success_response(
        message="Trending posts retrieved successfully",
        data={
            "posts": posts,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/stats")
async def get_posts_stats():
    """
    Get post statistics for filter badges (like Stack Overflow).
    
    Returns counts for:
    - All questions
    - Active (recently updated)
    - Unanswered (no replies)
    - Answered (has replies)
    - Trending (high activity last 7 days)
    """
    db = Database.get_db()
    post_service = PostService(db)
    
    stats = await post_service.get_posts_statistics()
    
    return success_response(
        message="Post statistics retrieved successfully",
        data=stats
    )


@router.get("/search")
async def search_posts(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Search posts by title or body content.
    """
    db = Database.get_db()
    post_service = PostService(db)
    
    skip = (page - 1) * limit
    posts = await post_service.search_posts(q, skip, limit)
    
    # Convert to JSON
    for post in posts:
        convert_post_to_json(post)
    
    return success_response(
        message="Search results retrieved successfully",
        data={
            "posts": posts,
            "query": q,
            "count": len(posts)
        }
    )


@router.get("/{identifier}")
async def get_post(identifier: str):
    """
    Get a single post by ID or slug and increment view count.
    
    - If identifier is a valid 24-character hex string, treats it as post_id
    - Otherwise, treats it as a slug
    """
    db = Database.get_db()
    post_service = PostService(db)
    
    # Check if identifier is a valid ObjectId (24 hex characters)
    is_object_id = len(identifier) == 24 and all(c in '0123456789abcdef' for c in identifier.lower())
    
    if is_object_id:
        post = await post_service.get_post_by_id(identifier)
    else:
        post = await post_service.get_post_by_slug(identifier)
    
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    # Increment view count
    post_id = str(post["_id"])
    await post_service.increment_view_count(post_id)
    post["view_count"] = post.get("view_count", 0) + 1
    
    # Convert to JSON
    convert_post_to_json(post)
    
    return success_response(
        message="Post retrieved successfully",
        data={"post": post}
    )


@router.post("/{post_id}/update")
async def update_post(
    post_id: str,
    title: Optional[str] = Form(None, min_length=5, max_length=200),
    category_id: Optional[str] = Form(None),
    subcategory_id: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    body: Optional[str] = Form(None, min_length=20),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a post. Only the author can update their post.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    post_service = PostService(db)
    category_service = CategoryService(db)
    
    # Check if post exists and user is author
    post = await post_service.get_post_by_id(post_id)
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    if post["author_id"] != str(current_user["_id"]):
        return error_response(
            message="You can only update your own posts",
            status_code=403
        )
    
    # Validate category if provided
    effective_category_id = category_id or post.get("category_id")
    if category_id:
        category = await category_service.get_category_by_id(category_id)
        if not category:
            return validation_error_response(
                message="Invalid category",
                errors={"category_id": "Category not found"}
            )
        # If category is a subcategory (has parent), reject it
        if category.get("parent_id"):
            return validation_error_response(
                message="Invalid category",
                errors={"category_id": "Cannot use a subcategory as the main category"}
            )
    
    # Validate subcategory if provided
    if subcategory_id:
        subcategory = await category_service.get_category_by_id(subcategory_id)
        if not subcategory:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory not found"}
            )
        # Validate subcategory belongs to the (new or existing) parent category
        if subcategory.get("parent_id") != effective_category_id:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory doesn't belong to the selected category"}
            )
    
    # Build update data
    update_data = {}
    if title:
        update_data["title"] = title
    if category_id:
        update_data["category_id"] = category_id
    if subcategory_id is not None:
        update_data["subcategory_id"] = subcategory_id if subcategory_id else None
    if body:
        update_data["body"] = body
    if tags is not None:
        tag_list = [t.strip().lower() for t in tags.split(',') if t.strip()]
        update_data["tags"] = list(set(tag_list))[:10]
    
    if not update_data:
        return validation_error_response(
            message="No fields to update",
            errors={"update": "At least one field must be provided"}
        )
    
    success = await post_service.update_post(post_id, update_data)
    
    if success:
        updated_post = await post_service.get_post_by_id(post_id)
        convert_post_to_json(updated_post)
        
        return success_response(
            message="Post updated successfully",
            data={"post": updated_post}
        )
    else:
        return error_response(
            message="Failed to update post"
        )


@router.post("/{post_id}/delete")
async def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a post. Only the author can delete their post.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    post_service = PostService(db)
    
    # Check if post exists and user is author
    post = await post_service.get_post_by_id(post_id)
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    if post["author_id"] != str(current_user["_id"]):
        return error_response(
            message="You can only delete your own posts",
            status_code=403
        )
    
    # Delete file attachments
    for attachment in post.get("attachments", []):
        await FileUploadService.delete_file(attachment["file_url"])
    
    success = await post_service.delete_post(post_id)
    
    if success:
        return success_response(
            message="Post deleted successfully",
            data={"post_id": post_id}
        )
    else:
        return error_response(
            message="Failed to delete post"
        )


@router.post("/{post_id}/vote")
async def vote_on_post(
    post_id: str,
    vote_type: str = Form(..., pattern="^(upvote|downvote)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Vote on a post (upvote or downvote).
    Users can:
    - Upvote or downvote a post
    - Remove their vote by clicking the same button
    - Change their vote from upvote to downvote or vice versa
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    post_service = PostService(db)
    
    post = await post_service.get_post_by_id(post_id)
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    # Pass user_id to track votes
    user_id = str(current_user["_id"])
    success, message, vote_info = await post_service.vote_post(post_id, user_id, vote_type)
    
    if not success:
        return error_response(message=message)
    
    return success_response(
        message=message,
        data={
            "post_id": post_id,
            "vote_info": vote_info
        }
    )


@router.post("/{post_id}/solve")
async def mark_post_solved(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a post as solved. Only the author can mark their post as solved.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    post_service = PostService(db)
    
    post = await post_service.get_post_by_id(post_id)
    if not post:
        return error_response(
            message="Post not found",
            status_code=404
        )
    
    if post["author_id"] != str(current_user["_id"]):
        return error_response(
            message="Only the author can mark their post as solved",
            status_code=403
        )
    
    # Check if post is already solved (final decision - cannot be undone)
    if post.get("is_solved", False):
        return error_response(
            message="This question is already marked as completed. Once marked as completed, it cannot be changed.",
            status_code=400
        )
    
    success = await post_service.mark_solved(post_id)
    
    if success:
        return success_response(
            message="Post marked as solved. This is a final decision and cannot be undone.",
            data={"post_id": post_id}
        )
    else:
        return error_response(
            message="Failed to mark post as solved. The post may already be marked as completed."
        )


# Admin-only endpoints
@router.post("/{post_id}/pin")
async def toggle_pin_post(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Toggle post pin status (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # TODO: Add admin permission check
    
    db = Database.get_db()
    post_service = PostService(db)
    
    success = await post_service.toggle_pin(post_id)
    
    if success:
        return success_response(
            message="Post pin status toggled",
            data={"post_id": post_id}
        )
    else:
        return error_response(
            message="Failed to toggle pin status"
        )


@router.post("/{post_id}/lock")
async def toggle_lock_post(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Toggle post lock status (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # TODO: Add admin permission check
    
    db = Database.get_db()
    post_service = PostService(db)
    
    success = await post_service.toggle_lock(post_id)
    
    if success:
        return success_response(
            message="Post lock status toggled",
            data={"post_id": post_id}
        )
    else:
        return error_response(
            message="Failed to toggle lock status"
        )


# DISABLED: User doesn't want comments on questions
# Only answers and comments on answers are allowed
#
# @router.post("/{post_id}/comment")
# async def add_comment_to_post(
#     post_id: str,
#     body: str = Form(..., min_length=10, max_length=500),
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Add a comment directly to a post (question).
#     This is different from answering - comments are for clarifications,
#     short questions, or brief feedback on the post itself.
#     
#     Max length: 500 characters (shorter than answers)
#     """
#     if not current_user:
#         return error_response(
#             message="Authentication required",
#             status_code=401
#         )
#     
#     db = Database.get_db()
#     post_service = PostService(db)
#     
#     # Import CommentService here to avoid circular import
#     from app.services.forum.comment import CommentService
#     comment_service = CommentService(db)
#     
#     # Verify post exists
#     post = await post_service.get_post_by_id(post_id)
#     if not post:
#         return error_response(
#             message="Post not found",
#             status_code=404
#         )
#     
#     # Check if post is locked
#     if post.get("is_locked", False):
#         return error_response(
#             message="Post is locked. Cannot add comments.",
#             status_code=403
#         )
#     
#     try:
#         # Create comment with is_post_comment flag
#         comment = await comment_service.create_comment(
#             post_id=post_id,
#             author_id=str(current_user["_id"]),
#             author_name=current_user.get("full_name", current_user.get("email")),
#             body=body,
#             attachments=[],
#             parent_id=None,
#             is_post_comment=True  # Mark as comment on post, not an answer
#         )
#         
#         # Convert datetime to ISO format
#         if comment.get("created_at"):
#             comment["created_at"] = comment["created_at"].isoformat()
#         if comment.get("updated_at"):
#             comment["updated_at"] = comment["updated_at"].isoformat()
#         
#         comment["id"] = str(comment["_id"])
#         del comment["_id"]
#         
#         # Remove voter arrays from response
#         comment.pop("upvoters", None)
#         comment.pop("downvoters", None)
#         
#         return success_response(
#             message="Comment added successfully",
#             data={"comment": comment},
#             status_code=201
#         )
#         
#     except Exception as e:
#         return error_response(
#             message=f"Failed to add comment: {str(e)}",
#             status_code=500
#         )
#
#
# @router.get("/{post_id}/comments")
# async def get_post_comments(
#     post_id: str,
#     page: int = Query(1, ge=1),
#     limit: int = Query(50, ge=1, le=100)
# ):
#     """
#     Get comments on a post (not answers, but actual comments on the question itself).
#     Returns only is_post_comment=True entries.
#     """
#     db = Database.get_db()
#     post_service = PostService(db)
#     
#     from app.services.forum.comment import CommentService
#     comment_service = CommentService(db)
#     
#     # Verify post exists
#     post = await post_service.get_post_by_id(post_id)
#     if not post:
#         return error_response(
#             message="Post not found",
#             status_code=404
#         )
#     
#     # Get post comments (not answers)
#     skip = (page - 1) * limit
#     
#     comments_cursor = comment_service.collection.find({
#         "post_id": post_id,
#         "is_post_comment": True,
#         "$or": [
#             {"is_deleted": {"$exists": False}},
#             {"is_deleted": False}
#         ]
#     }).sort("created_at", 1).skip(skip).limit(limit)
#     
#     comments = await comments_cursor.to_list(length=limit)
#     
#     # Count total
#     total = await comment_service.collection.count_documents({
#         "post_id": post_id,
#         "is_post_comment": True,
#         "$or": [
#             {"is_deleted": {"$exists": False}},
#             {"is_deleted": False}
#         ]
#     })
#     
#     # Convert to JSON
#     comments_data = []
#     for comment in comments:
#         comment["id"] = str(comment["_id"])
#         del comment["_id"]
#         if comment.get("created_at"):
#             comment["created_at"] = comment["created_at"].isoformat()
#         if comment.get("updated_at"):
#             comment["updated_at"] = comment["updated_at"].isoformat()
#         comment.pop("upvoters", None)
#         comment.pop("downvoters", None)
#         comments_data.append(comment)
#     
#     return success_response(
#         message="Post comments retrieved successfully",
#         data={
#             "comments": comments_data,
#             "pagination": {
#                 "total": total,
#                 "page": page,
#                 "limit": limit,
#                 "total_pages": (total + limit - 1) // limit
#             }
#         }
#     )
