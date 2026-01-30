from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId


class TagService:
    """Service for tag operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.tags
        self.posts_collection = db.posts
    
    async def _get_tag_usage_count(self, tag_slug: str) -> int:
        """
        Calculate actual usage count for a tag from posts collection.
        Only counts non-deleted posts.
        """
        return await self.posts_collection.count_documents({
            "tags": tag_slug,
            "$or": [
                {"is_deleted": {"$exists": False}},
                {"is_deleted": False}
            ]
        })
    
    async def _add_usage_counts(self, tags: List[Dict]) -> List[Dict]:
        """Add dynamic usage counts to a list of tags"""
        for tag in tags:
            tag["usage_count"] = await self._get_tag_usage_count(tag["slug"])
        return tags
    
    async def create_tag(
        self,
        name: str,
        slug: str,
        description: Optional[str] = None,
        group: Optional[str] = None,
        color: Optional[str] = None
    ) -> Dict:
        """Create a new tag"""
        tag_data = {
            "name": name,
            "slug": slug,
            "description": description,
            "group": group,
            "color": color,
            "usage_count": 0,  # Legacy field, actual count is calculated dynamically
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(tag_data)
        tag = await self.collection.find_one({"_id": result.inserted_id})
        return tag
    
    async def get_tag_by_slug(self, slug: str) -> Optional[Dict]:
        """Get tag by slug with dynamic usage count"""
        tag = await self.collection.find_one({"slug": slug, "is_active": True})
        if tag:
            tag["usage_count"] = await self._get_tag_usage_count(tag["slug"])
        return tag
    
    async def get_tag_by_id(self, tag_id: str) -> Optional[Dict]:
        """Get tag by ID with dynamic usage count"""
        try:
            tag = await self.collection.find_one({"_id": ObjectId(tag_id), "is_active": True})
            if tag:
                tag["usage_count"] = await self._get_tag_usage_count(tag["slug"])
            return tag
        except:
            return None
    
    async def get_all_tags(self) -> List[Dict]:
        """Get all active tags with dynamic usage counts"""
        cursor = self.collection.find({"is_active": True}).sort("name", 1)
        tags = await cursor.to_list(length=None)
        return await self._add_usage_counts(tags)
    
    async def get_tags_by_group(self, group: str) -> List[Dict]:
        """Get tags by group with dynamic usage counts"""
        cursor = self.collection.find({
            "group": group,
            "is_active": True
        }).sort("name", 1)
        tags = await cursor.to_list(length=None)
        return await self._add_usage_counts(tags)
    
    async def get_popular_tags(self, limit: int = 50) -> List[Dict]:
        """Get most used tags (calculated dynamically)"""
        # Get all active tags
        cursor = self.collection.find({"is_active": True})
        tags = await cursor.to_list(length=None)
        
        # Calculate actual usage counts
        tags = await self._add_usage_counts(tags)
        
        # Sort by usage_count descending and limit
        tags.sort(key=lambda x: x["usage_count"], reverse=True)
        
        return tags[:limit]
    
    async def search_tags(self, query: str) -> List[Dict]:
        """Search tags by name with dynamic usage counts"""
        cursor = self.collection.find({
            "name": {"$regex": query, "$options": "i"},
            "is_active": True
        }).limit(20)
        tags = await cursor.to_list(length=None)
        return await self._add_usage_counts(tags)
    
    async def update_tag(self, tag_id: str, update_data: Dict) -> bool:
        """Update a tag"""
        update_data["updated_at"] = datetime.utcnow()
        result = await self.collection.update_one(
            {"_id": ObjectId(tag_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def delete_tag(self, tag_id: str) -> bool:
        """Soft delete a tag"""
        result = await self.collection.update_one(
            {"_id": ObjectId(tag_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    async def increment_usage_count(self, tag_id: str):
        """
        Legacy method - kept for backward compatibility.
        Usage count is now calculated dynamically, so this is a no-op.
        """
        # No longer needed - usage counts are calculated dynamically
        pass
    
    async def decrement_usage_count(self, tag_id: str):
        """
        Legacy method - kept for backward compatibility.
        Usage count is now calculated dynamically, so this is a no-op.
        """
        # No longer needed - usage counts are calculated dynamically
        pass
    
    async def recalculate_usage_counts(self):
        """
        Legacy method - no longer needed since counts are calculated dynamically.
        Kept for backward compatibility.
        """
        # No longer needed - usage counts are calculated dynamically
        return 0
