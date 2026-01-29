from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict
from datetime import datetime, timedelta
from bson import ObjectId


class LeaderboardService:
    """Service for global leaderboard - calculates from real user data"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users = db.users
        self.posts = db.posts
        self.comments = db.comments
        self.contest_participants = db.contest_participants
    
    def _get_rank_badge(self, reputation: int) -> str:
        """Determine rank badge based on reputation"""
        if reputation >= 50000:
            return "Grandmaster"
        elif reputation >= 25000:
            return "Master"
        elif reputation >= 10000:
            return "Expert"
        elif reputation >= 5000:
            return "Advanced"
        elif reputation >= 1000:
            return "Intermediate"
        elif reputation >= 100:
            return "Beginner"
        else:
            return "Novice"
    
    async def get_top_contributors(self, limit: int = 10, time_period: str = "all_time") -> List[Dict]:
        """
        Get top contributors by reputation (calculated in real-time).
        NO MOCK DATA - all calculations from database.
        
        time_period: "all_time", "this_month", "this_week", "today"
        """
        try:
            # Calculate date filter based on time period
            now = datetime.utcnow()
            date_filter = {}
            
            if time_period == "today":
                date_filter = {"$gte": now.replace(hour=0, minute=0, second=0, microsecond=0)}
            elif time_period == "this_week":
                week_start = now - timedelta(days=now.weekday())
                date_filter = {"$gte": week_start.replace(hour=0, minute=0, second=0, microsecond=0)}
            elif time_period == "this_month":
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                date_filter = {"$gte": month_start}
            # "all_time" - no filter
            
            # Get all users
            users = await self.users.find({
                "is_active": True
            }).to_list(length=None)
            
            # Calculate reputation for each user
            user_reputations = []
            
            for user in users:
                user_id = str(user["_id"])
                
                # Build query for posts
                posts_query = {
                    "author_id": user_id,
                    "$or": [
                        {"is_deleted": {"$exists": False}},
                        {"is_deleted": False}
                    ]
                }
                if date_filter:
                    posts_query["created_at"] = date_filter
                
                # Get user's posts
                posts = await self.posts.find(posts_query).to_list(length=None)
                
                # Build query for answers
                answers_query = {
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
                }
                if date_filter:
                    answers_query["created_at"] = date_filter
                
                # Get user's answers
                answers = await self.comments.find(answers_query).to_list(length=None)
                
                # Calculate reputation
                reputation = 0
                
                # From posts: +10 per upvote, -2 per downvote
                for post in posts:
                    reputation += post.get("upvote_count", 0) * 10
                    reputation -= post.get("downvote_count", 0) * 2
                
                # From answers: +10 per upvote, -2 per downvote, +15 if accepted
                for answer in answers:
                    reputation += answer.get("upvote_count", 0) * 10
                    reputation -= answer.get("downvote_count", 0) * 2
                    if answer.get("is_accepted", False):
                        reputation += 15
                
                reputation = max(0, reputation)
                
                # Count total answers
                total_answers = len(answers)
                
                # Count accepted answers
                accepted_answers = sum(1 for answer in answers if answer.get("is_accepted", False))
                
                # Calculate acceptance rate
                acceptance_rate = (accepted_answers / total_answers * 100) if total_answers > 0 else 0
                
                # Calculate total earnings from contests (real from database)
                earnings_pipeline = [
                    {
                        "$match": {
                            "user_id": user_id
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": "$earnings"}
                        }
                    }
                ]
                
                earnings_result = await self.contest_participants.aggregate(earnings_pipeline).to_list(length=1)
                total_earnings = earnings_result[0]["total"] if earnings_result else 0
                
                # Determine rank badge
                rank_badge = self._get_rank_badge(reputation)
                
                # Store user data with all calculated fields
                user_reputations.append({
                    "user_id": user_id,
                    "user_name": user.get("full_name") or user.get("email", "").split("@")[0],
                    "username": user.get("username") or user.get("full_name") or user.get("email", "").split("@")[0],
                    "profile_picture": user.get("profile_picture"),
                    "reputation": reputation,
                    "total_answers": total_answers,
                    "accepted_answers": accepted_answers,
                    "acceptance_rate": round(acceptance_rate, 1),
                    "total_earnings": total_earnings,
                    "rank_badge": rank_badge
                })
            
            # Sort by reputation (highest first)
            user_reputations.sort(key=lambda x: x["reputation"], reverse=True)
            
            # Get top N
            top_users = user_reputations[:limit]
            
            # Add rank and trend
            for idx, user in enumerate(top_users, 1):
                user["rank"] = idx
                
                # Add trend indicator (for now, based on reputation comparison)
                # TODO: Implement historical rank tracking for accurate trends
                if idx == 1:
                    user["trend"] = "stable"  # Top spot
                elif user["reputation"] > 30000:
                    user["trend"] = "up"  # High rep likely rising
                elif user["reputation"] < 20000:
                    user["trend"] = "down"  # Lower rep might be declining
                else:
                    user["trend"] = "stable"
            
            return top_users
            
        except Exception as e:
            print(f"Error getting top contributors: {str(e)}")
            return []
    
    async def get_user_rank(self, user_id: str) -> Dict:
        """Get specific user's rank and complete stats"""
        try:
            # Get all users with reputation
            top_contributors = await self.get_top_contributors(limit=10000)
            
            # Find user in list
            for user in top_contributors:
                if user["user_id"] == user_id:
                    return {
                        "rank": user["rank"],
                        "reputation": user["reputation"],
                        "total_answers": user["total_answers"],
                        "accepted_answers": user["accepted_answers"],
                        "acceptance_rate": user["acceptance_rate"],
                        "total_earnings": user["total_earnings"],
                        "rank_badge": user["rank_badge"],
                        "trend": user.get("trend", "stable"),
                        "total_users": len(top_contributors),
                        "username": user["username"],
                        "profile_picture": user.get("profile_picture")
                    }
            
            # User not found or has no reputation
            return {
                "rank": None,
                "reputation": 0,
                "total_answers": 0,
                "accepted_answers": 0,
                "acceptance_rate": 0,
                "total_earnings": 0,
                "rank_badge": "Novice",
                "trend": "stable",
                "total_users": len(top_contributors),
                "username": None,
                "profile_picture": None
            }
            
        except Exception as e:
            print(f"Error getting user rank: {str(e)}")
            return {
                "rank": None,
                "reputation": 0,
                "total_answers": 0,
                "accepted_answers": 0,
                "acceptance_rate": 0,
                "total_earnings": 0,
                "rank_badge": "Novice",
                "trend": "stable",
                "total_users": 0,
                "username": None,
                "profile_picture": None
            }
