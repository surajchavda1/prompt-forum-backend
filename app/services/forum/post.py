from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId
import re


class PostService:
    """Service for post/question operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.posts
    
    def _get_username_lookup_pipeline(self) -> List[Dict]:
        """
        Returns aggregation pipeline stages to lookup user info from users collection.
        Adds 'username', 'full_name', 'profile_picture' fields and updates 'author_name'.
        """
        return [
            # Convert author_id string to ObjectId for lookup
            {
                "$addFields": {
                    "author_oid": {"$toObjectId": "$author_id"}
                }
            },
            # Lookup user from users collection
            {
                "$lookup": {
                    "from": "users",
                    "localField": "author_oid",
                    "foreignField": "_id",
                    "as": "author_info"
                }
            },
            # Extract user fields from author_info array
            {
                "$addFields": {
                    "username": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$author_info.username", 0]},
                            "$author_name"  # Fallback to stored author_name
                        ]
                    },
                    "full_name": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$author_info.full_name", 0]},
                            "$author_name"  # Fallback to stored author_name
                        ]
                    },
                    # Override author_name with current full_name from users collection
                    "author_name": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$author_info.full_name", 0]},
                            "$author_name"  # Keep stored value if lookup fails
                        ]
                    },
                    "profile_picture": {
                        "$arrayElemAt": ["$author_info.profile_picture", 0]
                    }
                }
            },
            # Remove temporary fields
            {
                "$project": {
                    "author_oid": 0,
                    "author_info": 0
                }
            }
        ]
    
    @staticmethod
    def generate_slug(title: str, post_id: str = None) -> str:
        """Generate URL-friendly slug from title"""
        # Convert to lowercase
        slug = title.lower()
        
        # Replace spaces and special characters with hyphens
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        # Limit length
        if len(slug) > 100:
            slug = slug[:100].rstrip('-')
        
        # Add unique identifier if post_id provided
        if post_id:
            slug = f"{slug}-{post_id[:8]}"
        
        return slug
    
    async def create_post(
        self,
        title: str,
        category_id: str,
        subcategory_id: Optional[str],
        tags: List[str],
        body: str,
        author_id: str,
        author_name: str,
        attachments: List[dict] = None
    ) -> Dict:
        """Create a new post"""
        post_data = {
            "title": title,
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "tags": tags if tags else [],
            "body": body,
            "author_id": author_id,
            "author_name": author_name,
            "slug": "",  # Will be updated after insert
            "view_count": 0,
            "reply_count": 0,
            "upvote_count": 0,
            "downvote_count": 0,
            "is_pinned": False,
            "is_locked": False,
            "is_solved": False,
            "attachments": attachments if attachments else [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(post_data)
        post_id = str(result.inserted_id)
        
        # Update slug with post ID
        slug = self.generate_slug(title, post_id)
        await self.collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"slug": slug}}
        )
        
        # Get and return the created post
        post = await self.collection.find_one({"_id": result.inserted_id})
        return post
    
    async def get_post_by_id(self, post_id: str) -> Optional[Dict]:
        """Get post by ID, includes author username"""
        try:
            pipeline = [
                {"$match": {"_id": ObjectId(post_id)}},
                *self._get_username_lookup_pipeline()
            ]
            cursor = self.collection.aggregate(pipeline)
            posts = await cursor.to_list(length=1)
            return posts[0] if posts else None
        except:
            return None
    
    async def get_post_by_slug(self, slug: str) -> Optional[Dict]:
        """Get post by slug, includes author username"""
        pipeline = [
            {"$match": {"slug": slug}},
            *self._get_username_lookup_pipeline()
        ]
        cursor = self.collection.aggregate(pipeline)
        posts = await cursor.to_list(length=1)
        return posts[0] if posts else None
    
    async def get_posts(
        self,
        category_id: Optional[str] = None,
        subcategory_id: Optional[str] = None,
        tag: Optional[str] = None,
        author_id: Optional[str] = None,
        is_solved: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: int = -1
    ) -> List[Dict]:
        """Get posts with filters and pagination, includes author username via lookup"""
        # Build match query
        match_query = {}
        
        if category_id:
            match_query["category_id"] = category_id
        if subcategory_id:
            match_query["subcategory_id"] = subcategory_id
        if tag:
            match_query["tags"] = tag
        if author_id:
            match_query["author_id"] = author_id
        if is_solved is not None:
            match_query["is_solved"] = is_solved
        
        # Aggregation pipeline with $lookup to get username
        pipeline = [
            {"$match": match_query},
            {"$sort": {sort_by: sort_order}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def count_posts(
        self,
        category_id: Optional[str] = None,
        subcategory_id: Optional[str] = None,
        tag: Optional[str] = None,
        author_id: Optional[str] = None
    ) -> int:
        """Count posts with filters"""
        query = {}
        
        if category_id:
            query["category_id"] = category_id
        if subcategory_id:
            query["subcategory_id"] = subcategory_id
        if tag:
            query["tags"] = tag
        if author_id:
            query["author_id"] = author_id
        
        return await self.collection.count_documents(query)
    
    async def search_posts(self, search_query: str, skip: int = 0, limit: int = 20) -> List[Dict]:
        """Search posts by title or body, includes author username"""
        match_query = {
            "$or": [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"body": {"$regex": search_query, "$options": "i"}}
            ]
        }
        
        pipeline = [
            {"$match": match_query},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def get_active_posts(self, skip: int = 0, limit: int = 20) -> List[Dict]:
        """
        Get recently active posts (sorted by updated_at).
        Posts with recent activity appear first, includes author username.
        """
        pipeline = [
            {"$sort": {"updated_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def get_unanswered_posts(self, skip: int = 0, limit: int = 20) -> List[Dict]:
        """
        Get posts with no replies (reply_count = 0), includes author username.
        """
        pipeline = [
            {"$match": {"reply_count": 0}},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def count_unanswered_posts(self) -> int:
        """Count posts with no replies"""
        return await self.collection.count_documents({"reply_count": 0})
    
    async def get_answered_posts(self, skip: int = 0, limit: int = 20) -> List[Dict]:
        """
        Get posts with at least one reply (reply_count > 0), includes author username.
        """
        pipeline = [
            {"$match": {"reply_count": {"$gt": 0}}},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def count_answered_posts(self) -> int:
        """Count posts with replies"""
        return await self.collection.count_documents({"reply_count": {"$gt": 0}})
    
    async def get_trending_posts(self, skip: int = 0, limit: int = 20) -> List[Dict]:
        """
        Get trending posts from last 7 days based on activity score, includes author username.
        Score = (upvotes * 3) + (replies * 2) + (views * 0.1)
        """
        from datetime import timedelta
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Use aggregation to calculate trending score
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": seven_days_ago}
                }
            },
            {
                "$addFields": {
                    "trending_score": {
                        "$add": [
                            {"$multiply": ["$upvote_count", 3]},
                            {"$multiply": ["$reply_count", 2]},
                            {"$multiply": ["$view_count", 0.1]}
                        ]
                    }
                }
            },
            {"$sort": {"trending_score": -1}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def count_trending_posts(self) -> int:
        """Count trending posts (created in last 7 days)"""
        from datetime import timedelta
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        return await self.collection.count_documents({
            "created_at": {"$gte": seven_days_ago}
        })
    
    async def get_posts_statistics(self) -> Dict:
        """
        Get comprehensive post statistics for filter badges.
        Returns counts for all filter categories.
        """
        from datetime import timedelta
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Run all counts in parallel for better performance
        all_count = await self.collection.count_documents({})
        unanswered_count = await self.collection.count_documents({"reply_count": 0})
        answered_count = await self.collection.count_documents({"reply_count": {"$gt": 0}})
        trending_count = await self.collection.count_documents({
            "created_at": {"$gte": seven_days_ago}
        })
        
        # Active = posts updated in last 24 hours
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        active_count = await self.collection.count_documents({
            "updated_at": {"$gte": one_day_ago}
        })
        
        return {
            "all": all_count,
            "active": active_count,
            "unanswered": unanswered_count,
            "answered": answered_count,
            "trending": trending_count
        }
    
    async def update_post(self, post_id: str, update_data: Dict) -> bool:
        """Update a post"""
        update_data["updated_at"] = datetime.utcnow()
        
        # If title is being updated, regenerate slug
        if "title" in update_data:
            update_data["slug"] = self.generate_slug(update_data["title"], post_id)
        
        result = await self.collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def delete_post(self, post_id: str) -> bool:
        """Delete a post"""
        result = await self.collection.delete_one({"_id": ObjectId(post_id)})
        return result.deleted_count > 0
    
    async def increment_view_count(self, post_id: str):
        """Increment post view count"""
        await self.collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"view_count": 1}}
        )
    
    async def increment_reply_count(self, post_id: str):
        """Increment post reply count"""
        await self.collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"reply_count": 1}}
        )
    
    async def vote_post(self, post_id: str, user_id: str, vote_type: str):
        """
        Vote on a post (upvote/downvote)
        Returns: (success: bool, message: str, vote_info: dict)
        """
        # Get current post to check existing votes
        post = await self.collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            return False, "Post not found", None
        
        # PERMISSION CHECK: Prevent voting on own post
        if post.get("author_id") == user_id:
            return False, "You cannot vote on your own post", None
        
        # Initialize vote tracking arrays if they don't exist
        upvoters = post.get("upvoters", [])
        downvoters = post.get("downvoters", [])
        
        # Check if user has already voted
        has_upvoted = user_id in upvoters
        has_downvoted = user_id in downvoters
        
        update_operations = {}
        message = ""
        
        if vote_type == "upvote":
            if has_upvoted:
                # User already upvoted - remove upvote
                update_operations = {
                    "$pull": {"upvoters": user_id},
                    "$inc": {"upvote_count": -1}
                }
                message = "Upvote removed"
            elif has_downvoted:
                # User has downvoted - switch to upvote
                update_operations = {
                    "$pull": {"downvoters": user_id},
                    "$addToSet": {"upvoters": user_id},
                    "$inc": {"upvote_count": 1, "downvote_count": -1}
                }
                message = "Changed to upvote"
            else:
                # New upvote
                update_operations = {
                    "$addToSet": {"upvoters": user_id},
                    "$inc": {"upvote_count": 1}
                }
                message = "Upvoted successfully"
                
        elif vote_type == "downvote":
            if has_downvoted:
                # User already downvoted - remove downvote
                update_operations = {
                    "$pull": {"downvoters": user_id},
                    "$inc": {"downvote_count": -1}
                }
                message = "Downvote removed"
            elif has_upvoted:
                # User has upvoted - switch to downvote
                update_operations = {
                    "$pull": {"upvoters": user_id},
                    "$addToSet": {"downvoters": user_id},
                    "$inc": {"downvote_count": 1, "upvote_count": -1}
                }
                message = "Changed to downvote"
            else:
                # New downvote
                update_operations = {
                    "$addToSet": {"downvoters": user_id},
                    "$inc": {"downvote_count": 1}
                }
                message = "Downvoted successfully"
        
        # Update the post
        if update_operations:
            update_operations["$set"] = {"updated_at": datetime.utcnow()}
            result = await self.collection.update_one(
                {"_id": ObjectId(post_id)},
                update_operations
            )
            
            if result.modified_count > 0:
                # Get updated counts
                updated_post = await self.collection.find_one({"_id": ObjectId(post_id)})
                vote_info = {
                    "upvote_count": updated_post.get("upvote_count", 0),
                    "downvote_count": updated_post.get("downvote_count", 0),
                    "user_vote": None if (vote_type == "upvote" and has_upvoted) or (vote_type == "downvote" and has_downvoted) else vote_type
                }
                return True, message, vote_info
        
        return False, "Failed to update vote", None
    
    async def toggle_pin(self, post_id: str) -> bool:
        """Toggle post pin status"""
        post = await self.get_post_by_id(post_id)
        if not post:
            return False
        
        new_status = not post.get("is_pinned", False)
        result = await self.collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"is_pinned": new_status, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    async def get_user_vote_status(self, post_id: str, user_id: str):
        """
        Get the user's vote status for a post
        Returns: "upvote", "downvote", or None
        """
        post = await self.collection.find_one(
            {"_id": ObjectId(post_id)},
            {"upvoters": 1, "downvoters": 1}
        )
        
        if not post:
            return None
        
        upvoters = post.get("upvoters", [])
        downvoters = post.get("downvoters", [])
        
        if user_id in upvoters:
            return "upvote"
        elif user_id in downvoters:
            return "downvote"
        return None
    
    async def toggle_lock(self, post_id: str) -> bool:
        """Toggle post lock status"""
        post = await self.get_post_by_id(post_id)
        if not post:
            return False
        
        new_status = not post.get("is_locked", False)
        result = await self.collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"is_locked": new_status, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    async def mark_solved(self, post_id: str) -> bool:
        """
        Mark post as solved.
        Once marked as solved, it cannot be undone (final decision).
        """
        # Check if post is already solved
        post = await self.get_post_by_id(post_id)
        if not post:
            return False
        
        # If already solved, cannot be changed (final decision)
        if post.get("is_solved", False):
            return False
        
        result = await self.collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"is_solved": True, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
