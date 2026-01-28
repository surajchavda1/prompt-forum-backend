from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId


class TagService:
    """Service for tag operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.tags
    
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
            "usage_count": 0,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(tag_data)
        tag = await self.collection.find_one({"_id": result.inserted_id})
        return tag
    
    async def get_tag_by_slug(self, slug: str) -> Optional[Dict]:
        """Get tag by slug"""
        return await self.collection.find_one({"slug": slug, "is_active": True})
    
    async def get_tag_by_id(self, tag_id: str) -> Optional[Dict]:
        """Get tag by ID"""
        try:
            return await self.collection.find_one({"_id": ObjectId(tag_id), "is_active": True})
        except:
            return None
    
    async def get_all_tags(self) -> List[Dict]:
        """Get all active tags"""
        cursor = self.collection.find({"is_active": True}).sort("name", 1)
        return await cursor.to_list(length=None)
    
    async def get_tags_by_group(self, group: str) -> List[Dict]:
        """Get tags by group"""
        cursor = self.collection.find({
            "group": group,
            "is_active": True
        }).sort("name", 1)
        return await cursor.to_list(length=None)
    
    async def get_popular_tags(self, limit: int = 50) -> List[Dict]:
        """Get most used tags"""
        cursor = self.collection.find({"is_active": True}).sort("usage_count", -1).limit(limit)
        return await cursor.to_list(length=None)
    
    async def search_tags(self, query: str) -> List[Dict]:
        """Search tags by name"""
        cursor = self.collection.find({
            "name": {"$regex": query, "$options": "i"},
            "is_active": True
        }).limit(20)
        return await cursor.to_list(length=None)
    
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
        """Increment usage count for a tag"""
        await self.collection.update_one(
            {"_id": ObjectId(tag_id)},
            {"$inc": {"usage_count": 1}}
        )
