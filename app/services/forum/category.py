from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId


class CategoryService:
    """Service for category operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.categories
    
    async def create_category(
        self,
        name: str,
        slug: str,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
        icon: Optional[str] = None,
        order: int = 0
    ) -> Dict:
        """Create a new category"""
        category_data = {
            "name": name,
            "slug": slug,
            "description": description,
            "parent_id": parent_id,
            "icon": icon,
            "order": order,
            "post_count": 0,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(category_data)
        category = await self.collection.find_one({"_id": result.inserted_id})
        return category
    
    async def get_category_by_slug(self, slug: str) -> Optional[Dict]:
        """Get category by slug"""
        return await self.collection.find_one({"slug": slug, "is_active": True})
    
    async def get_category_by_id(self, category_id: str) -> Optional[Dict]:
        """Get category by ID"""
        try:
            return await self.collection.find_one({"_id": ObjectId(category_id), "is_active": True})
        except:
            return None
    
    async def get_all_categories(self) -> List[Dict]:
        """Get all active categories"""
        cursor = self.collection.find({"is_active": True}).sort("order", 1)
        return await cursor.to_list(length=None)
    
    async def get_parent_categories(self) -> List[Dict]:
        """Get all parent categories (no parent_id)"""
        cursor = self.collection.find({
            "parent_id": None,
            "is_active": True
        }).sort("order", 1)
        return await cursor.to_list(length=None)
    
    async def get_subcategories(self, parent_id: str) -> List[Dict]:
        """Get subcategories of a parent category"""
        cursor = self.collection.find({
            "parent_id": parent_id,
            "is_active": True
        }).sort("order", 1)
        return await cursor.to_list(length=None)
    
    async def get_categories_with_subcategories(self) -> List[Dict]:
        """Get all parent categories with their subcategories"""
        parents = await self.get_parent_categories()
        
        for parent in parents:
            parent["subcategories"] = await self.get_subcategories(str(parent["_id"]))
        
        return parents
    
    async def update_category(self, category_id: str, update_data: Dict) -> bool:
        """Update a category"""
        update_data["updated_at"] = datetime.utcnow()
        result = await self.collection.update_one(
            {"_id": ObjectId(category_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def delete_category(self, category_id: str) -> bool:
        """Soft delete a category"""
        result = await self.collection.update_one(
            {"_id": ObjectId(category_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    async def increment_post_count(self, category_id: str):
        """Increment post count for a category"""
        await self.collection.update_one(
            {"_id": ObjectId(category_id)},
            {"$inc": {"post_count": 1}}
        )
    
    async def get_top_categories(self, limit: int = 10) -> List[Dict]:
        """
        Get top categories sorted by post count.
        Shows most popular categories like Stack Overflow's tag sidebar.
        
        Args:
            limit: Number of top categories to return (default 10)
        
        Returns:
            List of categories with highest post counts
        """
        cursor = self.collection.find({
            "is_active": True,
            "post_count": {"$gt": 0}  # Only categories with posts
        }).sort("post_count", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
