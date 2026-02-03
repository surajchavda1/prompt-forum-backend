from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime
from typing import Optional, List


class CommentService:
    """Service for managing comments/answers"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.comments
    
    def _get_username_lookup_pipeline(self) -> List[dict]:
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
    
    async def create_comment(
        self,
        post_id: str,
        author_id: str,
        author_name: str,
        body: str,
        attachments: List[dict] = [],
        parent_id: Optional[str] = None,  # For nested replies
        is_post_comment: bool = False  # NEW: True if comment on post, False if answer
    ) -> dict:
        """
        Create a new comment/answer or reply to existing comment
        
        is_post_comment: 
          - True: Short comment on the post itself (like Stack Overflow comments on questions)
          - False: Full answer/solution to the post (default)
        """
        comment = {
            "post_id": post_id,
            "parent_id": parent_id,  # null for top-level, comment_id for replies
            "author_id": author_id,
            "author_name": author_name,
            "body": body,
            "upvote_count": 0,
            "downvote_count": 0,
            "reply_count": 0,  # Track number of replies
            "upvoters": [],
            "downvoters": [],
            "is_accepted": False,
            "is_edited": False,
            "is_post_comment": is_post_comment,  # NEW: Distinguish post comments from answers
            "attachments": attachments,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(comment)
        comment["_id"] = result.inserted_id
        
        # If this is a reply, increment parent's reply_count
        if parent_id:
            await self.increment_reply_count(parent_id)
        
        return comment
    
    async def get_comment_by_id(self, comment_id: str) -> Optional[dict]:
        """Get comment by ID, includes author username"""
        try:
            pipeline = [
                {"$match": {"_id": ObjectId(comment_id)}},
                *self._get_username_lookup_pipeline()
            ]
            cursor = self.collection.aggregate(pipeline)
            comments = await cursor.to_list(length=1)
            return comments[0] if comments else None
        except:
            return None
    
    async def get_comments_by_post(
        self,
        post_id: str,
        sort_by: str = "created_at",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 50,
        include_replies: bool = False  # NEW: Option to include/exclude replies
    ) -> List[dict]:
        """
        Get all top-level comments for a post with sorting, includes author username.
        (excludes nested replies by default)
        
        sort_by: created_at, upvote_count
        sort_order: asc, desc
        include_replies: if True, returns all comments; if False, only top-level (parent_id = null)
        """
        skip = (page - 1) * limit
        sort_direction = -1 if sort_order == "desc" else 1
        
        # Build match query - only top-level answers by default (exclude post comments and replies)
        match_query = {
            "post_id": post_id,
            "$and": [
                # Not deleted
                {
                    "$or": [
                        {"is_deleted": {"$exists": False}},
                        {"is_deleted": False}
                    ]
                },
                # Not a post comment (show only answers)
                {
                    "$or": [
                        {"is_post_comment": {"$exists": False}},
                        {"is_post_comment": False}
                    ]
                }
            ]
        }
        
        # Filter for top-level comments only (exclude nested replies)
        if not include_replies:
            match_query["$and"].append({
                "$or": [
                    {"parent_id": None},
                    {"parent_id": {"$exists": False}}
                ]
            })
        
        pipeline = [
            {"$match": match_query},
            {"$sort": {sort_by: sort_direction}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def count_comments(self, post_id: str, include_replies: bool = False) -> int:
        """
        Count total top-level answers for a post
        (excludes nested replies, deleted comments, and post comments by default)
        """
        query = {
            "post_id": post_id,
            "$and": [
                # Not deleted
                {
                    "$or": [
                        {"is_deleted": {"$exists": False}},
                        {"is_deleted": False}
                    ]
                },
                # Not a post comment (count only answers)
                {
                    "$or": [
                        {"is_post_comment": {"$exists": False}},
                        {"is_post_comment": False}
                    ]
                }
            ]
        }
        
        # Exclude replies if requested
        if not include_replies:
            query["$and"].append({
                "$or": [
                    {"parent_id": None},
                    {"parent_id": {"$exists": False}}
                ]
            })
        
        return await self.collection.count_documents(query)
    
    async def update_comment(
        self,
        comment_id: str,
        body: Optional[str] = None,
        attachments: Optional[List[dict]] = None
    ) -> bool:
        """Update a comment"""
        update_data = {
            "updated_at": datetime.utcnow(),
            "is_edited": True
        }
        
        if body is not None:
            update_data["body"] = body
        
        if attachments is not None:
            update_data["attachments"] = attachments
        
        result = await self.collection.update_one(
            {"_id": ObjectId(comment_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def delete_comment(self, comment_id: str) -> bool:
        """Soft delete a comment"""
        result = await self.collection.update_one(
            {"_id": ObjectId(comment_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    async def vote_comment(self, comment_id: str, user_id: str, vote_type: str):
        """
        Vote on a comment (upvote/downvote)
        Returns: (success: bool, message: str, vote_info: dict)
        """
        # Get current comment to check existing votes
        comment = await self.collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            return False, "Comment not found", None
        
        # PERMISSION CHECK: Prevent voting on own comment
        if comment.get("author_id") == user_id:
            return False, "You cannot vote on your own comment", None
        
        # Initialize vote tracking arrays if they don't exist
        upvoters = comment.get("upvoters", [])
        downvoters = comment.get("downvoters", [])
        
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
        
        # Update the comment
        if update_operations:
            update_operations["$set"] = {"updated_at": datetime.utcnow()}
            result = await self.collection.update_one(
                {"_id": ObjectId(comment_id)},
                update_operations
            )
            
            if result.modified_count > 0:
                # Get updated counts
                updated_comment = await self.collection.find_one({"_id": ObjectId(comment_id)})
                vote_info = {
                    "upvote_count": updated_comment.get("upvote_count", 0),
                    "downvote_count": updated_comment.get("downvote_count", 0),
                    "user_vote": None if (vote_type == "upvote" and has_upvoted) or (vote_type == "downvote" and has_downvoted) else vote_type
                }
                return True, message, vote_info
        
        return False, "Failed to update vote", None
    
    async def accept_comment(self, comment_id: str, post_id: str) -> bool:
        """
        Mark a comment as accepted solution.
        Only one comment can be accepted per post.
        Note: Caller should check if post is already solved before calling this method.
        Once a post is marked as solved, it cannot be unmarked (final decision).
        """
        # First, unaccept any previously accepted comments for this post
        await self.collection.update_many(
            {"post_id": post_id, "is_accepted": True},
            {"$set": {"is_accepted": False, "updated_at": datetime.utcnow()}}
        )
        
        # Accept the new comment
        result = await self.collection.update_one(
            {"_id": ObjectId(comment_id)},
            {"$set": {"is_accepted": True, "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
    
    async def unaccept_comment(self, comment_id: str) -> bool:
        """Remove accepted status from a comment"""
        result = await self.collection.update_one(
            {"_id": ObjectId(comment_id)},
            {"$set": {"is_accepted": False, "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
    
    async def get_user_vote_status(self, comment_id: str, user_id: str):
        """
        Get the user's vote status for a comment
        Returns: "upvote", "downvote", or None
        """
        comment = await self.collection.find_one(
            {"_id": ObjectId(comment_id)},
            {"upvoters": 1, "downvoters": 1}
        )
        
        if not comment:
            return None
        
        upvoters = comment.get("upvoters", [])
        downvoters = comment.get("downvoters", [])
        
        if user_id in upvoters:
            return "upvote"
        elif user_id in downvoters:
            return "downvote"
        return None
    
    async def increment_reply_count(self, comment_id: str) -> bool:
        """Increment reply count for a comment"""
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(comment_id)},
                {"$inc": {"reply_count": 1}}
            )
            return result.modified_count > 0
        except:
            return False
    
    async def decrement_reply_count(self, comment_id: str) -> bool:
        """Decrement reply count for a comment"""
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(comment_id)},
                {"$inc": {"reply_count": -1}}
            )
            return result.modified_count > 0
        except:
            return False
    
    async def get_replies(self, comment_id: str, skip: int = 0, limit: int = 50) -> List[dict]:
        """Get all replies to a specific comment (excludes deleted), includes author username"""
        pipeline = [
            {
                "$match": {
                    "parent_id": comment_id,
                    "$or": [
                        {"is_deleted": {"$exists": False}},
                        {"is_deleted": False}
                    ]
                }
            },
            {"$sort": {"created_at": 1}},
            {"$skip": skip},
            {"$limit": limit},
            *self._get_username_lookup_pipeline()
        ]
        
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def count_replies(self, comment_id: str) -> int:
        """Count replies to a comment (excludes deleted)"""
        return await self.collection.count_documents({
            "parent_id": comment_id,
            "$or": [
                {"is_deleted": {"$exists": False}},
                {"is_deleted": False}
            ]
        })
