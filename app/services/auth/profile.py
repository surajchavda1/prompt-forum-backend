from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from bson import ObjectId
import re
from app.models.auth.profile import (
    UserStatistics,
    Badge,
    TopTag,
    TopPost,
    UserProfileResponse,
    ProfileUpdate
)


class ProfileService:
    """Service for user profile operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users_collection = db.users
        self.posts_collection = db.posts
        self.comments_collection = db.comments
    
    async def is_username_available(self, username: str, exclude_user_id: Optional[str] = None) -> bool:
        """
        Check if a username is available.
        
        Args:
            username: The username to check
            exclude_user_id: User ID to exclude from check (for updates)
        
        Returns:
            True if username is available, False otherwise
        """
        query = {
            "username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}
        }
        
        if exclude_user_id:
            query["_id"] = {"$ne": ObjectId(exclude_user_id)}
        
        existing = await self.users_collection.find_one(query)
        return existing is None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username (case-insensitive)"""
        return await self.users_collection.find_one({
            "username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}
        })
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Get complete user profile with statistics"""
        try:
            # Get user basic info
            user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return None
            
            # Calculate statistics
            stats = await self.calculate_user_statistics(user_id)
            
            # Get badges
            badges = await self.calculate_user_badges(user_id, stats)
            
            # Get top tags
            top_tags = await self.get_user_top_tags(user_id, limit=5)
            
            # Get top posts
            top_posts = await self.get_user_top_posts(user_id, limit=4)
            
            # Build profile response
            profile = {
                "id": str(user["_id"]),
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "username": user.get("username") or user.get("full_name") or user.get("email", "").split("@")[0],
                "profile_picture": user.get("profile_picture"),
                "cover_image": user.get("cover_image"),
                "title": user.get("title"),
                "location": user.get("location"),
                "website": user.get("website"),
                "about_me": user.get("about_me"),
                "is_verified": user.get("is_verified", False),
                "joined_date": user.get("created_at").isoformat() if user.get("created_at") else None,
                "statistics": stats,
                "badges": badges,
                "top_tags": top_tags,
                "top_posts": top_posts
            }
            
            return profile
            
        except Exception as e:
            print(f"Error getting user profile: {str(e)}")
            return None
    
    async def calculate_user_statistics(self, user_id: str) -> Dict:
        """Calculate user statistics from posts and comments"""
        try:
            # Get all user's questions (posts)
            user_posts = await self.posts_collection.find({
                "author_id": user_id,
                "$or": [
                    {"is_deleted": {"$exists": False}},
                    {"is_deleted": False}
                ]
            }).to_list(length=None)
            
            # Get all user's answers (comments that are not post comments and not replies)
            user_answers = await self.comments_collection.find({
                "author_id": user_id,
                "$or": [
                    {"is_post_comment": {"$exists": False}},
                    {"is_post_comment": False}
                ],
                "$and": [
                    {
                        "$or": [
                            {"parent_id": None},
                            {"parent_id": {"$exists": False}}
                        ]
                    },
                    {
                        "$or": [
                            {"is_deleted": {"$exists": False}},
                            {"is_deleted": False}
                        ]
                    }
                ]
            }).to_list(length=None)
            
            # Calculate reputation (upvotes - downvotes)
            reputation = 0
            
            # From posts: +10 per upvote, -2 per downvote
            for post in user_posts:
                reputation += post.get("upvote_count", 0) * 10
                reputation -= post.get("downvote_count", 0) * 2
            
            # From answers: +10 per upvote, -2 per downvote, +15 if accepted
            for answer in user_answers:
                reputation += answer.get("upvote_count", 0) * 10
                reputation -= answer.get("downvote_count", 0) * 2
                if answer.get("is_accepted", False):
                    reputation += 15
            
            # Ensure reputation is not negative
            reputation = max(0, reputation)
            
            # Count accepted answers
            accepted_answers = sum(1 for answer in user_answers if answer.get("is_accepted", False))
            
            # Total views (sum of all user's questions)
            total_views = sum(post.get("view_count", 0) for post in user_posts)
            
            # Calculate global rank (based on reputation)
            users_with_higher_rep = await self.users_collection.count_documents({
                "reputation": {"$gt": reputation}
            })
            global_rank = users_with_higher_rep + 1
            
            return {
                "reputation": reputation,
                "global_rank": global_rank,
                "accepted_answers": accepted_answers,
                "total_answers": len(user_answers),
                "total_questions": len(user_posts),
                "total_views": total_views,
                "impact": total_views
            }
            
        except Exception as e:
            print(f"Error calculating statistics: {str(e)}")
            return {
                "reputation": 0,
                "global_rank": None,
                "accepted_answers": 0,
                "total_answers": 0,
                "total_questions": 0,
                "total_views": 0,
                "impact": 0
            }
    
    async def calculate_user_badges(self, user_id: str, stats: Dict) -> Dict:
        """
        Calculate user badges based on achievements.
        
        Badge criteria:
        - Gold: Reputation milestones (10k, 25k, 50k), 100+ accepted answers
        - Silver: Reputation milestones (5k, 10k), 50+ accepted answers, popular questions
        - Bronze: First question, first answer, first upvote, etc.
        """
        gold = 0
        silver = 0
        bronze = 0
        
        reputation = stats.get("reputation", 0)
        accepted = stats.get("accepted_answers", 0)
        questions = stats.get("total_questions", 0)
        answers = stats.get("total_answers", 0)
        
        # Gold badges (rare achievements)
        if reputation >= 50000:
            gold += 1
        if reputation >= 25000:
            gold += 1
        if reputation >= 10000:
            gold += 1
        if accepted >= 100:
            gold += 1
        if accepted >= 500:
            gold += 1
        if stats.get("total_views", 0) >= 1000000:
            gold += 1
        
        # Silver badges (notable achievements)
        if reputation >= 5000:
            silver += 1
        if reputation >= 2500:
            silver += 1
        if reputation >= 1000:
            silver += 1
        if accepted >= 50:
            silver += 1
        if accepted >= 25:
            silver += 1
        if questions >= 50:
            silver += 1
        if answers >= 100:
            silver += 1
        if stats.get("total_views", 0) >= 100000:
            silver += 1
        
        # Bronze badges (common achievements)
        if questions >= 1:
            bronze += 1  # Asked first question
        if answers >= 1:
            bronze += 1  # Posted first answer
        if reputation >= 100:
            bronze += 1
        if reputation >= 500:
            bronze += 1
        if accepted >= 1:
            bronze += 1  # First accepted answer
        if accepted >= 10:
            bronze += 1
        if questions >= 10:
            bronze += 1
        if answers >= 10:
            bronze += 1
        if answers >= 50:
            bronze += 1
        
        return {
            "gold": gold,
            "silver": silver,
            "bronze": bronze
        }
    
    async def get_user_top_tags(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get user's most used tags from their posts"""
        try:
            # Aggregate tags from user's posts
            pipeline = [
                {
                    "$match": {
                        "author_id": user_id,
                        "$or": [
                            {"is_deleted": {"$exists": False}},
                            {"is_deleted": False}
                        ]
                    }
                },
                {"$unwind": "$tags"},
                {
                    "$group": {
                        "_id": "$tags",
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": limit}
            ]
            
            results = await self.posts_collection.aggregate(pipeline).to_list(length=limit)
            
            top_tags = []
            for result in results:
                top_tags.append({
                    "name": result["_id"],
                    "count": result["count"]
                })
            
            return top_tags
            
        except Exception as e:
            print(f"Error getting top tags: {str(e)}")
            return []
    
    async def get_user_top_posts(self, user_id: str, limit: int = 4) -> List[Dict]:
        """Get user's top posts by votes"""
        try:
            posts = await self.posts_collection.find({
                "author_id": user_id,
                "$or": [
                    {"is_deleted": {"$exists": False}},
                    {"is_deleted": False}
                ]
            }).sort("upvote_count", -1).limit(limit).to_list(length=limit)
            
            top_posts = []
            for post in posts:
                top_posts.append({
                    "id": str(post["_id"]),
                    "title": post.get("title"),
                    "upvote_count": post.get("upvote_count", 0),
                    "view_count": post.get("view_count", 0),
                    "reply_count": post.get("reply_count", 0),
                    "created_at": post.get("created_at").isoformat() if post.get("created_at") else None,
                    "is_solved": post.get("is_solved", False)
                })
            
            return top_posts
            
        except Exception as e:
            print(f"Error getting top posts: {str(e)}")
            return []
    
    async def update_user_profile(
        self,
        user_id: str,
        profile_data: ProfileUpdate
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Update user profile information (username cannot be changed)"""
        try:
            # Build update data (only include non-None fields)
            update_data = {}
            if profile_data.full_name is not None:
                update_data["full_name"] = profile_data.full_name
            if profile_data.title is not None:
                update_data["title"] = profile_data.title
            if profile_data.location is not None:
                update_data["location"] = profile_data.location
            if profile_data.website is not None:
                update_data["website"] = profile_data.website
            if profile_data.about_me is not None:
                update_data["about_me"] = profile_data.about_me
            
            if not update_data:
                return False, "No fields to update", None
            
            update_data["updated_at"] = datetime.utcnow()
            
            # Update user
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                return False, "Profile not updated", None
            
            # Get updated profile
            updated_profile = await self.get_user_profile(user_id)
            
            return True, "Profile updated successfully", updated_profile
            
        except Exception as e:
            return False, f"Failed to update profile: {str(e)}", None
    
    async def update_profile_picture(self, user_id: str, image_url: str) -> bool:
        """Update user profile picture"""
        try:
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "profile_picture": image_url,
                    "updated_at": datetime.utcnow()
                }}
            )
            return result.modified_count > 0
        except:
            return False
    
    async def update_cover_image(self, user_id: str, image_url: str) -> bool:
        """Update user cover image"""
        try:
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "cover_image": image_url,
                    "updated_at": datetime.utcnow()
                }}
            )
            return result.modified_count > 0
        except:
            return False
    
    async def get_user_posts(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at"
    ) -> Tuple[List[Dict], int]:
        """Get user's questions/posts with pagination"""
        try:
            skip = (page - 1) * limit
            
            posts = await self.posts_collection.find({
                "author_id": user_id,
                "$or": [
                    {"is_deleted": {"$exists": False}},
                    {"is_deleted": False}
                ]
            }).sort(sort_by, -1).skip(skip).limit(limit).to_list(length=limit)
            
            total = await self.posts_collection.count_documents({
                "author_id": user_id,
                "$or": [
                    {"is_deleted": {"$exists": False}},
                    {"is_deleted": False}
                ]
            })
            
            # Convert ObjectId to string and handle datetime fields
            for post in posts:
                post["id"] = str(post["_id"])
                del post["_id"]
                if post.get("created_at"):
                    post["created_at"] = post["created_at"].isoformat()
                if post.get("updated_at"):
                    post["updated_at"] = post["updated_at"].isoformat()
                
                # Convert datetime in attachments
                if post.get("attachments"):
                    for attachment in post["attachments"]:
                        if attachment.get("uploaded_at"):
                            attachment["uploaded_at"] = attachment["uploaded_at"].isoformat()
            
            return posts, total
            
        except Exception as e:
            print(f"Error getting user posts: {str(e)}")
            return [], 0
    
    async def get_user_answers(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at"
    ) -> Tuple[List[Dict], int]:
        """Get user's answers with pagination"""
        try:
            skip = (page - 1) * limit
            
            answers = await self.comments_collection.find({
                "author_id": user_id,
                "$or": [
                    {"is_post_comment": {"$exists": False}},
                    {"is_post_comment": False}
                ],
                "$and": [
                    {
                        "$or": [
                            {"parent_id": None},
                            {"parent_id": {"$exists": False}}
                        ]
                    },
                    {
                        "$or": [
                            {"is_deleted": {"$exists": False}},
                            {"is_deleted": False}
                        ]
                    }
                ]
            }).sort(sort_by, -1).skip(skip).limit(limit).to_list(length=limit)
            
            total = await self.comments_collection.count_documents({
                "author_id": user_id,
                "$or": [
                    {"is_post_comment": {"$exists": False}},
                    {"is_post_comment": False}
                ],
                "$and": [
                    {
                        "$or": [
                            {"parent_id": None},
                            {"parent_id": {"$exists": False}}
                        ]
                    },
                    {
                        "$or": [
                            {"is_deleted": {"$exists": False}},
                            {"is_deleted": False}
                        ]
                    }
                ]
            })
            
            # Convert ObjectId to string and add post title
            for answer in answers:
                answer["id"] = str(answer["_id"])
                del answer["_id"]
                
                # Get post title
                post = await self.posts_collection.find_one(
                    {"_id": ObjectId(answer["post_id"])}
                )
                answer["post_title"] = post.get("title") if post else "Unknown"
                answer["post_slug"] = post.get("slug") if post else ""
                
                if answer.get("created_at"):
                    answer["created_at"] = answer["created_at"].isoformat()
                if answer.get("updated_at"):
                    answer["updated_at"] = answer["updated_at"].isoformat()
                
                # Convert datetime in attachments
                if answer.get("attachments"):
                    for attachment in answer["attachments"]:
                        if attachment.get("uploaded_at"):
                            attachment["uploaded_at"] = attachment["uploaded_at"].isoformat()
            
            return answers, total
            
        except Exception as e:
            print(f"Error getting user answers: {str(e)}")
            return [], 0
