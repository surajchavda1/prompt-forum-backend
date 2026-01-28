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
async def search_tags(q: str = Query(..., min_length=1)):
    """
    Search tags by name.
    """
    db = Database.get_db()
    tag_service = TagService(db)
    
    tags = await tag_service.search_tags(q)
    
    # Convert to JSON-serializable format
    for tag in tags:
        convert_tag_to_json(tag)
    
    return success_response(
        message="Search results retrieved successfully",
        data={"tags": tags, "query": q}
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
