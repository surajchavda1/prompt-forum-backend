from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from app.database import Database
from app.services.forum.tag import TagService
from app.models.forum.tag import (
    TagResponse,
    TagCreate,
    TagUpdate
)
from app.utils.response import success_response, error_response, validation_error_response
from app.routes.auth.dependencies import get_current_user

router = APIRouter(prefix="/tags", tags=["Tags"])


def convert_tag_to_json(tag: dict) -> dict:
    """Convert tag document to JSON-serializable format"""
    tag["id"] = str(tag["_id"])
    del tag["_id"]
    if tag.get("created_at"):
        tag["created_at"] = tag["created_at"].isoformat()
    if tag.get("updated_at"):
        tag["updated_at"] = tag["updated_at"].isoformat()
    return tag


@router.get("/all")
async def get_all_tags():
    """
    Get all tags.
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tags = await tag_service.get_all_tags()
    
    # Convert to JSON-serializable format
    for tag in tags:
        convert_tag_to_json(tag)
    
    return success_response(
        message="Tags retrieved successfully",
        data={"tags": tags}
    )


@router.get("/popular")
async def get_popular_tags(limit: int = Query(50, le=100)):
    """
    Get most popular/used tags.
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tags = await tag_service.get_popular_tags(limit=limit)
    
    # Convert to JSON-serializable format
    for tag in tags:
        convert_tag_to_json(tag)
    
    return success_response(
        message="Popular tags retrieved successfully",
        data={"tags": tags}
    )


@router.get("/subcategory/{subcategory_id}")
async def get_tags_by_subcategory(subcategory_id: str):
    """
    Get tags by subcategory ID.
    
    This is the main endpoint for the Category -> Subcategory -> Tags flow.
    When frontend selects a subcategory, call this endpoint to get available tags.
    
    Args:
        subcategory_id: The ID of the subcategory
    
    Returns:
        List of tags belonging to the specified subcategory
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tags = await tag_service.get_tags_by_subcategory(subcategory_id)
    
    # Convert to JSON-serializable format
    for tag in tags:
        convert_tag_to_json(tag)
    
    return success_response(
        message="Tags retrieved successfully",
        data={"tags": tags, "subcategory_id": subcategory_id}
    )


@router.get("/subcategory-slug/{subcategory_slug}")
async def get_tags_by_subcategory_slug(subcategory_slug: str):
    """
    Get tags by subcategory slug.
    
    Alternative endpoint using slug instead of ID.
    
    Args:
        subcategory_slug: The slug of the subcategory (e.g., "chatgpt-image-prompts")
    
    Returns:
        List of tags belonging to the specified subcategory
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tags = await tag_service.get_tags_by_subcategory_slug(subcategory_slug)
    
    # Convert to JSON-serializable format
    for tag in tags:
        convert_tag_to_json(tag)
    
    return success_response(
        message="Tags retrieved successfully",
        data={"tags": tags, "subcategory_slug": subcategory_slug}
    )


@router.get("/group/{group_name}")
async def get_tags_by_group(group_name: str):
    """
    Get tags by group name.
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tags = await tag_service.get_tags_by_group(group_name)
    
    # Convert to JSON-serializable format
    for tag in tags:
        convert_tag_to_json(tag)
    
    return success_response(
        message=f"Tags from group '{group_name}' retrieved successfully",
        data={"tags": tags, "group": group_name}
    )


@router.get("/search")
async def search_tags(
    q: str = Query(..., min_length=1),
    subcategory_id: Optional[str] = Query(None, description="Optional: Filter by subcategory ID")
):
    """
    Search tags by name.
    Optionally filter by subcategory_id for scoped search.
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tags = await tag_service.search_tags(q, subcategory_id=subcategory_id)
    
    # Convert to JSON-serializable format
    for tag in tags:
        convert_tag_to_json(tag)
    
    return success_response(
        message="Search results retrieved successfully",
        data={"tags": tags, "query": q, "subcategory_id": subcategory_id}
    )


@router.get("/{slug}")
async def get_tag_by_slug(slug: str):
    """
    Get a single tag by slug.
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tag = await tag_service.get_tag_by_slug(slug)
    
    if not tag:
        return error_response(
            message="Tag not found",
            status_code=404
        )
    
    # Convert to JSON-serializable format
    convert_tag_to_json(tag)
    
    return success_response(
        message="Tag retrieved successfully",
        data={"tag": tag}
    )


@router.post("/create")
async def create_tag(
    tag: TagCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new tag (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    tag_service = TagService(db)
    
    # Check if slug already exists
    existing = await tag_service.get_tag_by_slug(tag.slug)
    if existing:
        return validation_error_response(
            message="Tag with this slug already exists",
            errors={"slug": "Already exists"}
        )
    
    new_tag = await tag_service.create_tag(
        name=tag.name,
        slug=tag.slug,
        description=tag.description,
        group=tag.group,
        color=tag.color
    )
    
    # Convert to JSON-serializable format
    convert_tag_to_json(new_tag)
    
    return success_response(
        message="Tag created successfully",
        data={"tag": new_tag}
    )


@router.post("/{tag_id}/update")
async def update_tag(
    tag_id: str,
    update_data: TagUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a tag (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    tag_service = TagService(db)
    
    # Check if tag exists
    tag = await tag_service.get_tag_by_id(tag_id)
    if not tag:
        return error_response(
            message="Tag not found",
            status_code=404
        )
    
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    
    success = await tag_service.update_tag(tag_id, update_dict)
    
    if success:
        updated_tag = await tag_service.get_tag_by_id(tag_id)
        convert_tag_to_json(updated_tag)
        
        return success_response(
            message="Tag updated successfully",
            data={"tag": updated_tag}
        )
    else:
        return error_response(
            message="Failed to update tag"
        )


@router.post("/{tag_id}/delete")
async def delete_tag(
    tag_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a tag (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    tag_service = TagService(db)
    
    # Check if tag exists
    tag = await tag_service.get_tag_by_id(tag_id)
    if not tag:
        return error_response(
            message="Tag not found",
            status_code=404
        )
    
    success = await tag_service.delete_tag(tag_id)
    
    if success:
        return success_response(
            message="Tag deleted successfully",
            data={"tag_id": tag_id}
        )
    else:
        return error_response(
            message="Failed to delete tag"
        )


@router.post("/recalculate-counts")
async def recalculate_tag_counts(
    current_user: dict = Depends(get_current_user)
):
    """
    Recalculate usage counts for all tags based on actual post usage.
    
    This endpoint:
    - Counts how many active posts use each tag
    - Updates the usage_count field for all tags
    - Returns statistics about the recalculation
    
    Admin only - add permission check later.
    
    Use this when:
    - Tag counts seem incorrect
    - After data migration
    - After bulk post operations
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    tag_service = TagService(db)
    
    # Get all active posts
    posts = await db.posts.find({
        "$or": [
            {"is_deleted": {"$exists": False}},
            {"is_deleted": False}
        ]
    }).to_list(length=None)
    
    # Count tag usage in posts
    tag_usage = {}
    posts_with_tags = 0
    
    for post in posts:
        post_tags = post.get("tags", [])
        if post_tags:
            posts_with_tags += 1
            for tag_slug in post_tags:
                tag_usage[tag_slug] = tag_usage.get(tag_slug, 0) + 1
    
    # Get all tags
    all_tags = await tag_service.get_all_tags()
    
    # Update each tag
    updated_count = 0
    fixed_tags = []
    
    for tag in all_tags:
        tag_slug = tag["slug"]
        actual_count = tag_usage.get(tag_slug, 0)
        current_count = tag.get("usage_count", 0)
        
        # Update if different
        if current_count != actual_count:
            await tag_service.update_tag(
                str(tag["_id"]),
                {"usage_count": actual_count}
            )
            updated_count += 1
            fixed_tags.append({
                "name": tag["name"],
                "slug": tag_slug,
                "old_count": current_count,
                "new_count": actual_count
            })
    
    # Get top used tags
    top_tags = sorted(tag_usage.items(), key=lambda x: x[1], reverse=True)[:10]
    top_tags_list = [{"slug": slug, "count": count} for slug, count in top_tags]
    
    # Get tags with zero usage
    zero_usage_tags = [tag["name"] for tag in all_tags if tag_usage.get(tag["slug"], 0) == 0]
    
    return success_response(
        message="Tag counts recalculated successfully",
        data={
            "summary": {
                "total_posts": len(posts),
                "posts_with_tags": posts_with_tags,
                "unique_tags_used": len(tag_usage),
                "total_tags_in_db": len(all_tags),
                "tags_updated": updated_count,
                "tags_with_zero_usage": len(zero_usage_tags)
            },
            "fixed_tags": fixed_tags,
            "top_10_tags": top_tags_list,
            "zero_usage_tags": zero_usage_tags[:20]  # First 20 only
        }
    )
