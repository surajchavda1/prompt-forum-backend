from fastapi import APIRouter, Query
from typing import Optional
from app.database import Database
from app.utils.response import success_response, error_response
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/search", tags=["Search"])


def convert_object_ids(doc: dict) -> dict:
    """Convert ObjectIds and dates to JSON-serializable format"""
    try:
        if "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        
        # Convert ALL datetime fields recursively
        for key, value in list(doc.items()):
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, ObjectId):
                doc[key] = str(value)
            elif isinstance(value, list):
                # Handle lists (like attachments)
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        doc[key][i] = convert_object_ids(item)
                    elif isinstance(item, datetime):
                        doc[key][i] = item.isoformat()
            elif isinstance(value, dict):
                doc[key] = convert_object_ids(value)
        
        return doc
    except Exception as e:
        print(f"Error converting doc: {e}")
        return doc


@router.get("")
async def global_search(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Results per category"),
    page: int = Query(1, ge=1, description="Page number"),
    categories: Optional[str] = Query(None, description="Filter categories: posts,contests,tags,categories (comma-separated)")
):
    """
    Global search across all content types.
    
    Searches in:
    - **Posts/Questions**: title, body, tags
    - **Contests**: title, description, category, tags
    - **Tags**: name, description
    - **Categories**: name, description
    
    **Query Parameters:**
    - `q`: Search query (required, 1-100 chars)
    - `limit`: Results per category (1-50, default: 10)
    - `page`: Page number (default: 1)
    - `categories`: Filter specific types (e.g., "posts,contests")
    
    **Example:**
    ```
    GET /api/search?q=prompt&limit=5
    GET /api/search?q=ai&categories=posts,contests
    ```
    
    **Response:**
    ```json
    {
      "success": true,
      "data": {
        "query": "prompt",
        "results": {
          "posts": [...],
          "contests": [...],
          "tags": [...],
          "categories": [...]
        },
        "counts": {
          "posts": 10,
          "contests": 5,
          "tags": 3,
          "categories": 2,
          "total": 20
        }
      }
    }
    ```
    """
    db = Database.get_db()
    
    # Parse category filter
    enabled_categories = ["posts", "contests", "tags", "categories"]
    if categories:
        enabled_categories = [c.strip().lower() for c in categories.split(",") if c.strip()]
        # Validate
        valid_cats = ["posts", "contests", "tags", "categories"]
        enabled_categories = [c for c in enabled_categories if c in valid_cats]
        if not enabled_categories:
            enabled_categories = valid_cats
    
    # Calculate skip for pagination
    skip = (page - 1) * limit
    
    # Create search regex pattern (case-insensitive)
    search_pattern = {"$regex": q, "$options": "i"}
    
    results = {}
    counts = {}
    
    # 1. SEARCH POSTS/QUESTIONS
    if "posts" in enabled_categories:
        posts_query = {
            "$and": [
                {
                    "$or": [
                        {"title": search_pattern},
                        {"body": search_pattern},
                        {"tags": search_pattern}
                    ]
                },
                {
                    "$or": [
                        {"is_deleted": {"$exists": False}},
                        {"is_deleted": False}
                    ]
                }
            ]
        }
        
        # Get total count
        posts_count = await db.posts.count_documents(posts_query)
        
        # Get paginated results
        posts_cursor = db.posts.find(posts_query).sort("created_at", -1).skip(skip).limit(limit)
        posts = await posts_cursor.to_list(length=limit)
        
        # Convert to JSON
        for post in posts:
            convert_object_ids(post)
            # Add snippet (first 150 chars of body)
            if "body" in post:
                post["snippet"] = post["body"][:150] + ("..." if len(post["body"]) > 150 else "")
        
        results["posts"] = posts
        counts["posts"] = posts_count
    else:
        results["posts"] = []
        counts["posts"] = 0
    
    # 2. SEARCH CONTESTS
    if "contests" in enabled_categories:
        contests_query = {
            "$and": [
                {
                    "$or": [
                        {"title": search_pattern},
                        {"description": search_pattern},
                        {"category": search_pattern},
                        {"tags": search_pattern}
                    ]
                },
                {"owner_id": {"$exists": True}}
            ]
        }
        
        # Get total count
        contests_count = await db.contests.count_documents(contests_query)
        
        # Get paginated results
        contests_cursor = db.contests.find(contests_query).sort("created_at", -1).skip(skip).limit(limit)
        contests = await contests_cursor.to_list(length=limit)
        
        # Convert to JSON and add snippet
        for contest in contests:
            convert_object_ids(contest)
            if "description" in contest:
                contest["snippet"] = contest["description"][:150] + ("..." if len(contest["description"]) > 150 else "")
        
        results["contests"] = contests
        counts["contests"] = contests_count
    else:
        results["contests"] = []
        counts["contests"] = 0
    
    # 3. SEARCH TAGS
    if "tags" in enabled_categories:
        tags_query = {
            "$and": [
                {
                    "$or": [
                        {"name": search_pattern},
                        {"slug": search_pattern},
                        {"description": search_pattern}
                    ]
                },
                {"is_active": True}
            ]
        }
        
        # Get total count
        tags_count = await db.tags.count_documents(tags_query)
        
        # Get paginated results (sorted by usage)
        tags_cursor = db.tags.find(tags_query).sort("usage_count", -1).skip(skip).limit(limit)
        tags = await tags_cursor.to_list(length=limit)
        
        # Convert to JSON
        for tag in tags:
            convert_object_ids(tag)
        
        results["tags"] = tags
        counts["tags"] = tags_count
    else:
        results["tags"] = []
        counts["tags"] = 0
    
    # 4. SEARCH CATEGORIES
    if "categories" in enabled_categories:
        categories_query = {
            "$and": [
                {
                    "$or": [
                        {"name": search_pattern},
                        {"description": search_pattern},
                        {"slug": search_pattern}
                    ]
                },
                {"is_active": True}
            ]
        }
        
        # Get total count
        categories_count = await db.categories.count_documents(categories_query)
        
        # Get paginated results
        categories_cursor = db.categories.find(categories_query).sort("name", 1).skip(skip).limit(limit)
        categories_list = await categories_cursor.to_list(length=limit)
        
        # Convert to JSON
        for category in categories_list:
            convert_object_ids(category)
        
        results["categories"] = categories_list
        counts["categories"] = categories_count
    else:
        results["categories"] = []
        counts["categories"] = 0
    
    # Calculate total
    total_count = sum(counts.values())
    
    return success_response(
        message=f"Search completed successfully",
        data={
            "query": q,
            "results": results,
            "counts": counts,
            "total_results": total_count,
            "pagination": {
                "page": page,
                "limit": limit,
                "has_more": any(count > skip + limit for count in counts.values())
            }
        }
    )


@router.get("/suggestions")
async def search_suggestions(
    q: str = Query(..., min_length=1, max_length=50, description="Search query for autocomplete"),
    limit: int = Query(5, ge=1, le=10, description="Number of suggestions")
):
    """
    Get search suggestions/autocomplete for quick search.
    
    Returns only titles/names for fast autocomplete:
    - Post titles
    - Contest titles
    - Tag names
    - Category names
    
    **Example:**
    ```
    GET /api/search/suggestions?q=pro&limit=5
    ```
    
    **Response:**
    ```json
    {
      "success": true,
      "data": {
        "suggestions": [
          {
            "type": "post",
            "title": "Prompt Engineering Best Practices",
            "id": "..."
          },
          {
            "type": "contest",
            "title": "Professional Prompt Challenge",
            "id": "..."
          },
          {
            "type": "tag",
            "name": "prompt-engineering",
            "usage_count": 42
          }
        ]
      }
    }
    ```
    """
    db = Database.get_db()
    search_pattern = {"$regex": q, "$options": "i"}
    
    suggestions = []
    
    # Get post titles
    posts = await db.posts.find(
        {
            "title": search_pattern,
            "$or": [
                {"is_deleted": {"$exists": False}},
                {"is_deleted": False}
            ]
        }
    ).sort("view_count", -1).limit(limit).to_list(length=limit)
    
    for post in posts:
        suggestions.append({
            "type": "post",
            "id": str(post["_id"]),
            "title": post["title"],
            "view_count": post.get("view_count", 0)
        })
    
    # Get contest titles
    contests = await db.contests.find(
        {
            "title": search_pattern,
            "owner_id": {"$exists": True}
        }
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    for contest in contests:
        suggestions.append({
            "type": "contest",
            "id": str(contest["_id"]),
            "title": contest["title"],
            "status": contest.get("status")
        })
    
    # Get tag names
    tags = await db.tags.find(
        {
            "name": search_pattern,
            "is_active": True
        }
    ).sort("usage_count", -1).limit(limit).to_list(length=limit)
    
    for tag in tags:
        suggestions.append({
            "type": "tag",
            "id": str(tag["_id"]),
            "name": tag["name"],
            "slug": tag["slug"],
            "usage_count": tag.get("usage_count", 0)
        })
    
    # Get category names
    categories_list = await db.categories.find(
        {
            "name": search_pattern,
            "is_active": True
        }
    ).sort("name", 1).limit(limit).to_list(length=limit)
    
    for category in categories_list:
        suggestions.append({
            "type": "category",
            "id": str(category["_id"]),
            "name": category["name"],
            "slug": category.get("slug")
        })
    
    return success_response(
        message="Suggestions retrieved successfully",
        data={
            "query": q,
            "suggestions": suggestions[:limit * 2]  # Return top results from all types
        }
    )


@router.get("/trending")
async def get_trending_searches(
    limit: int = Query(10, ge=1, le=50, description="Number of trending items")
):
    """
    Get trending/popular content across the platform.
    
    Returns:
    - Most viewed posts (last 7 days)
    - Active contests
    - Popular tags
    
    **Example:**
    ```
    GET /api/search/trending?limit=5
    ```
    """
    db = Database.get_db()
    
    # Get trending posts (most viewed recently)
    trending_posts = await db.posts.find({
        "$or": [
            {"is_deleted": {"$exists": False}},
            {"is_deleted": False}
        ]
    }).sort("view_count", -1).limit(limit).to_list(length=limit)
    
    for post in trending_posts:
        convert_object_ids(post)
    
    # Get active contests
    trending_contests = await db.contests.find({
        "status": "ACTIVE",
        "owner_id": {"$exists": True}
    }).sort("participant_count", -1).limit(limit).to_list(length=limit)
    
    for contest in trending_contests:
        convert_object_ids(contest)
    
    # Get popular tags
    trending_tags = await db.tags.find({
        "is_active": True
    }).sort("usage_count", -1).limit(limit).to_list(length=limit)
    
    for tag in trending_tags:
        convert_object_ids(tag)
    
    return success_response(
        message="Trending content retrieved successfully",
        data={
            "trending_posts": trending_posts,
            "active_contests": trending_contests,
            "popular_tags": trending_tags
        }
    )
