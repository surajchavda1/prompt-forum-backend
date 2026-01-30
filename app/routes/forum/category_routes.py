from fastapi import APIRouter, Depends
from typing import List
from app.database import Database
from app.services.forum.category import CategoryService
from app.models.forum.category import (
    CategoryResponse,
    CategoryWithSubcategories,
    CategoryCreate,
    CategoryUpdate
)
from app.utils.response import success_response, error_response, validation_error_response
from app.routes.auth.dependencies import get_current_user

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/all")
async def get_all_categories():
    """
    Get all categories (flat list).
    """
    db = Database.get_db()
    category_service = CategoryService(db)
    
    categories = await category_service.get_all_categories()
    
    # Convert ObjectId and datetime to string
    for cat in categories:
        cat["id"] = str(cat["_id"])
        del cat["_id"]
        if cat.get("created_at"):
            cat["created_at"] = cat["created_at"].isoformat()
        if cat.get("updated_at"):
            cat["updated_at"] = cat["updated_at"].isoformat()
    
    return success_response(
        message="Categories retrieved successfully",
        data={"categories": categories}
    )


@router.get("/tree")
async def get_categories_tree():
    """
    Get categories in tree structure (parent with subcategories).
    """
    db = Database.get_db()
    category_service = CategoryService(db)
    
    categories = await category_service.get_categories_with_subcategories()
    
    # Convert ObjectId and datetime to string
    for parent in categories:
        parent["id"] = str(parent["_id"])
        del parent["_id"]
        if parent.get("created_at"):
            parent["created_at"] = parent["created_at"].isoformat()
        if parent.get("updated_at"):
            parent["updated_at"] = parent["updated_at"].isoformat()
        
        for sub in parent.get("subcategories", []):
            sub["id"] = str(sub["_id"])
            del sub["_id"]
            if sub.get("created_at"):
                sub["created_at"] = sub["created_at"].isoformat()
            if sub.get("updated_at"):
                sub["updated_at"] = sub["updated_at"].isoformat()
    
    return success_response(
        message="Category tree retrieved successfully",
        data={"categories": categories}
    )


@router.get("/parent")
async def get_parent_categories():
    """
    Get only parent categories (no subcategories).
    """
    db = Database.get_db()
    category_service = CategoryService(db)
    
    parents = await category_service.get_parent_categories()
    
    # Convert ObjectId and datetime to string
    for cat in parents:
        cat["id"] = str(cat["_id"])
        del cat["_id"]
        if cat.get("created_at"):
            cat["created_at"] = cat["created_at"].isoformat()
        if cat.get("updated_at"):
            cat["updated_at"] = cat["updated_at"].isoformat()
    
    return success_response(
        message="Parent categories retrieved successfully",
        data={"categories": parents}
    )


@router.get("/top")
async def get_top_categories(limit: int = 10):
    """
    Get top categories by post count.
    Similar to Stack Overflow's popular tags sidebar.
    
    Shows most active categories with their post counts.
    Perfect for displaying in sidebar or homepage.
    """
    from fastapi import Query
    
    db = Database.get_db()
    category_service = CategoryService(db)
    
    # Validate limit
    if limit < 1:
        limit = 10
    if limit > 50:
        limit = 50
    
    top_categories = await category_service.get_top_categories(limit)
    
    # Convert ObjectId and datetime to string
    for cat in top_categories:
        cat["id"] = str(cat["_id"])
        del cat["_id"]
        if cat.get("created_at"):
            cat["created_at"] = cat["created_at"].isoformat()
        if cat.get("updated_at"):
            cat["updated_at"] = cat["updated_at"].isoformat()
    
    return success_response(
        message="Top categories retrieved successfully",
        data={
            "categories": top_categories,
            "total": len(top_categories)
        }
    )


@router.get("/{identifier}")
async def get_category(identifier: str):
    """
    Get a single category by ID or slug.
    
    - If identifier is a valid 24-character hex string, treats it as category_id
    - Otherwise, treats it as a slug
    """
    db = Database.get_db()
    category_service = CategoryService(db)
    
    # Check if identifier is a valid ObjectId (24 hex characters)
    is_object_id = len(identifier) == 24 and all(c in '0123456789abcdef' for c in identifier.lower())
    
    if is_object_id:
        category = await category_service.get_category_by_id(identifier)
    else:
        category = await category_service.get_category_by_slug(identifier)
    
    if not category:
        return error_response(
            message="Category not found",
            status_code=404
        )
    
    # Get subcategories if it's a parent
    if not category.get("parent_id"):
        subcategories = await category_service.get_subcategories(str(category["_id"]))
        category["subcategories"] = subcategories
        
        for sub in category.get("subcategories", []):
            sub["id"] = str(sub["_id"])
            del sub["_id"]
            if sub.get("created_at"):
                sub["created_at"] = sub["created_at"].isoformat()
            if sub.get("updated_at"):
                sub["updated_at"] = sub["updated_at"].isoformat()
    
    # Convert ObjectId and datetime to string
    category["id"] = str(category["_id"])
    del category["_id"]
    if category.get("created_at"):
        category["created_at"] = category["created_at"].isoformat()
    if category.get("updated_at"):
        category["updated_at"] = category["updated_at"].isoformat()
    
    return success_response(
        message="Category retrieved successfully",
        data={"category": category}
    )


@router.post("/create")
async def create_category(
    category: CategoryCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new category (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    category_service = CategoryService(db)
    
    # Check if slug already exists
    existing = await category_service.get_category_by_slug(category.slug)
    if existing:
        return validation_error_response(
            message="Category with this slug already exists",
            errors={"slug": "Already exists"}
        )
    
    new_category = await category_service.create_category(
        name=category.name,
        slug=category.slug,
        description=category.description,
        parent_id=category.parent_id,
        icon=category.icon,
        order=category.order
    )
    
    # Convert ObjectId and datetime to string
    new_category["id"] = str(new_category["_id"])
    del new_category["_id"]
    if new_category.get("created_at"):
        new_category["created_at"] = new_category["created_at"].isoformat()
    if new_category.get("updated_at"):
        new_category["updated_at"] = new_category["updated_at"].isoformat()
    
    return success_response(
        message="Category created successfully",
        data={"category": new_category}
    )


@router.post("/{category_id}/update")
async def update_category(
    category_id: str,
    update_data: CategoryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a category (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    category_service = CategoryService(db)
    
    # Check if category exists
    category = await category_service.get_category_by_id(category_id)
    if not category:
        return error_response(
            message="Category not found",
            status_code=404
        )
    
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    
    success = await category_service.update_category(category_id, update_dict)
    
    if success:
        updated_category = await category_service.get_category_by_id(category_id)
        updated_category["id"] = str(updated_category["_id"])
        del updated_category["_id"]
        if updated_category.get("created_at"):
            updated_category["created_at"] = updated_category["created_at"].isoformat()
        if updated_category.get("updated_at"):
            updated_category["updated_at"] = updated_category["updated_at"].isoformat()
        
        return success_response(
            message="Category updated successfully",
            data={"category": updated_category}
        )
    else:
        return error_response(
            message="Failed to update category"
        )


@router.post("/{category_id}/delete")
async def delete_category(
    category_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a category (Admin only - add permission check later).
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    category_service = CategoryService(db)
    
    # Check if category exists
    category = await category_service.get_category_by_id(category_id)
    if not category:
        return error_response(
            message="Category not found",
            status_code=404
        )
    
    success = await category_service.delete_category(category_id)
    
    if success:
        return success_response(
            message="Category deleted successfully",
            data={"category_id": category_id}
        )
    else:
        return error_response(
            message="Failed to delete category"
        )
