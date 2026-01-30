"""
Contest Widgets Service
Provides data for contest details page sidebar widgets
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bson import ObjectId


class ContestWidgetsService:
    """Service for contest sidebar widgets and statistics"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.contests = db.contests
        self.tasks = db.contest_tasks
        self.participants = db.contest_participants
        self.submissions = db.contest_submissions
        self.users = db.users
    
    async def get_user_progress(self, contest_id: str, user_id: str) -> Optional[Dict]:
        """
        Get user's progress in a specific contest.
        
        Returns:
        - Rank in contest
        - Total score
        - Tasks completed/pending
        - Completion percentage
        """
        try:
            # Get participant record
            participant = await self.participants.find_one({
                "contest_id": contest_id,
                "user_id": user_id
            })
            
            if not participant:
                return None
            
            # Get contest to check total tasks
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            if not contest:
                return None
            
            # Get total tasks count
            total_tasks = await self.tasks.count_documents({
                "contest_id": contest_id
            })
            
            # Get user's submissions
            submissions = await self.submissions.find({
                "contest_id": contest_id,
                "user_id": user_id
            }).to_list(length=None)
            
            # Count by status
            completed_tasks = sum(1 for s in submissions if s.get("status") == "approved")
            pending_tasks = sum(1 for s in submissions if s.get("status") == "pending")
            revision_tasks = sum(1 for s in submissions if s.get("status") == "revision_requested")
            
            # Get user's rank
            all_participants = await self.participants.find({
                "contest_id": contest_id
            }).sort("total_score", -1).to_list(length=None)
            
            user_rank = None
            total_participants = len(all_participants)
            
            for idx, p in enumerate(all_participants, 1):
                if p["user_id"] == user_id:
                    user_rank = idx
                    break
            
            # Calculate completion percentage
            completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Convert joined_at to ISO format
            joined_at = participant.get("joined_at")
            if joined_at and hasattr(joined_at, 'isoformat'):
                joined_at = joined_at.isoformat()
            
            return {
                "rank": user_rank,
                "total_participants": total_participants,
                "total_score": participant.get("total_score", 0),
                "completed_tasks": completed_tasks,
                "pending_tasks": pending_tasks,
                "revision_tasks": revision_tasks,
                "total_tasks": total_tasks,
                "completion_percentage": round(completion_percentage, 1),
                "joined_at": joined_at,
                "approved_tasks": participant.get("approved_tasks", 0)
            }
            
        except Exception as e:
            print(f"Error getting user progress: {str(e)}")
            return None
    
    async def get_contest_stats(self, contest_id: str) -> Dict:
        """
        Get enhanced contest statistics.
        
        Returns:
        - Total participants
        - Total submissions
        - Completion rate
        - Most popular task
        - Average score
        - Active participants (submitted in last 24h)
        """
        try:
            # Get basic counts
            total_participants = await self.participants.count_documents({
                "contest_id": contest_id
            })
            
            total_submissions = await self.submissions.count_documents({
                "contest_id": contest_id
            })
            
            # Get all submissions for analysis
            submissions = await self.submissions.find({
                "contest_id": contest_id
            }).to_list(length=None)
            
            # Calculate approval rate
            approved_count = sum(1 for s in submissions if s.get("status") == "approved")
            approval_rate = (approved_count / len(submissions) * 100) if submissions else 0
            
            # Get task with most submissions
            task_submission_counts = {}
            for submission in submissions:
                task_id = submission.get("task_id")
                if task_id:
                    task_submission_counts[task_id] = task_submission_counts.get(task_id, 0) + 1
            
            most_popular_task_id = None
            most_popular_task_count = 0
            most_popular_task_title = None
            
            if task_submission_counts:
                most_popular_task_id = max(task_submission_counts, key=task_submission_counts.get)
                most_popular_task_count = task_submission_counts[most_popular_task_id]
                
                # Get task title
                task = await self.tasks.find_one({"_id": ObjectId(most_popular_task_id)})
                if task:
                    most_popular_task_title = task.get("title")
            
            # Calculate average score
            participants = await self.participants.find({
                "contest_id": contest_id
            }).to_list(length=None)
            
            total_score = sum(p.get("total_score", 0) for p in participants)
            average_score = (total_score / len(participants)) if participants else 0
            
            # Active participants (submitted in last 24h)
            day_ago = datetime.utcnow() - timedelta(days=1)
            recent_submissions = await self.submissions.count_documents({
                "contest_id": contest_id,
                "submitted_at": {"$gte": day_ago}
            })
            
            # Get contest for time remaining
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            time_remaining = None
            if contest and contest.get("end_date"):
                end_date = contest["end_date"]
                now = datetime.utcnow()
                if end_date > now:
                    delta = end_date - now
                    days = delta.days
                    hours = delta.seconds // 3600
                    
                    if days > 0:
                        time_remaining = f"{days} day{'s' if days != 1 else ''}"
                    else:
                        time_remaining = f"{hours} hour{'s' if hours != 1 else ''}"
                else:
                    time_remaining = "Ended"
            
            return {
                "total_participants": total_participants,
                "total_submissions": total_submissions,
                "approval_rate": round(approval_rate, 1),
                "average_score": round(average_score, 1),
                "most_popular_task": {
                    "task_id": most_popular_task_id,
                    "title": most_popular_task_title,
                    "submission_count": most_popular_task_count
                } if most_popular_task_id else None,
                "active_in_24h": recent_submissions,
                "time_remaining": time_remaining
            }
            
        except Exception as e:
            print(f"Error getting contest stats: {str(e)}")
            return {
                "total_participants": 0,
                "total_submissions": 0,
                "approval_rate": 0,
                "average_score": 0,
                "most_popular_task": None,
                "active_in_24h": 0,
                "time_remaining": None
            }
    
    async def get_contest_owner_info(self, owner_id: str, exclude_contest_id: str = None) -> Dict:
        """
        Get contest owner information and their other contests.
        
        Returns:
        - Owner profile
        - Total contests created
        - Average rating
        - Other active contests
        """
        try:
            # Get owner user info
            owner = await self.users.find_one({"_id": ObjectId(owner_id)})
            
            if not owner:
                return None
            
            # Get all contests by this owner
            query = {"owner_id": owner_id}
            if exclude_contest_id:
                query["_id"] = {"$ne": ObjectId(exclude_contest_id)}
            
            owner_contests = await self.contests.find(query).to_list(length=None)
            
            # Count total contests
            total_contests = len(owner_contests) + (1 if exclude_contest_id else 0)
            
            # Calculate average rating (if ratings exist)
            # TODO: Implement rating system later
            average_rating = 4.5  # Placeholder
            total_ratings = total_contests  # Placeholder
            
            # Get other active contests (limit to 3-5)
            other_contests = []
            for contest in owner_contests[:5]:
                if contest.get("status") in ["draft", "active"]:
                    # Convert end_date to ISO format
                    end_date = contest.get("end_date")
                    if end_date and hasattr(end_date, 'isoformat'):
                        end_date = end_date.isoformat()
                    
                    other_contests.append({
                        "id": str(contest["_id"]),
                        "title": contest.get("title"),
                        "total_prize": contest.get("total_prize"),
                        "status": contest.get("status"),
                        "participant_count": await self.participants.count_documents({
                            "contest_id": str(contest["_id"])
                        }),
                        "end_date": end_date
                    })
            
            return {
                "owner_id": owner_id,
                "username": owner.get("username") or owner.get("full_name") or owner.get("email", "").split("@")[0],
                "owner_name": owner.get("full_name") or owner.get("email", "").split("@")[0],
                "owner_email": owner.get("email"),
                "profile_picture": owner.get("profile_picture"),
                "total_contests": total_contests,
                "average_rating": average_rating,
                "total_ratings": total_ratings,
                "other_contests": other_contests
            }
            
        except Exception as e:
            print(f"Error getting owner info: {str(e)}")
            return None
    
    async def get_similar_contests(self, contest_id: str, limit: int = 5) -> List[Dict]:
        """
        Get similar/related contests based on category, difficulty, and tags.
        
        Returns contests that are:
        - Same category
        - Similar difficulty
        - Currently active or upcoming
        - Not the current contest
        """
        try:
            # Get current contest
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return []
            
            category = contest.get("category")
            difficulty = contest.get("difficulty")
            
            # Build query for similar contests
            query = {
                "_id": {"$ne": ObjectId(contest_id)},
                "status": {"$in": ["active", "draft"]},
                "$or": [
                    {"category": category},  # Same category
                    {"difficulty": difficulty}  # Same difficulty
                ]
            }
            
            # Get similar contests
            similar_contests = await self.contests.find(query).sort(
                "created_at", -1
            ).limit(limit * 2).to_list(length=limit * 2)  # Get extra to filter
            
            # Build response with participant counts
            results = []
            for c in similar_contests:
                contest_id_str = str(c["_id"])
                
                participant_count = await self.participants.count_documents({
                    "contest_id": contest_id_str
                })
                
                # Calculate time remaining
                time_remaining = None
                if c.get("end_date"):
                    end_date = c["end_date"]
                    now = datetime.utcnow()
                    if end_date > now:
                        delta = end_date - now
                        days = delta.days
                        if days > 0:
                            time_remaining = f"{days} day{'s' if days != 1 else ''}"
                        else:
                            hours = delta.seconds // 3600
                            time_remaining = f"{hours} hour{'s' if hours != 1 else ''}"
                
                results.append({
                    "id": contest_id_str,
                    "title": c.get("title"),
                    "total_prize": c.get("total_prize"),
                    "category": c.get("category"),
                    "difficulty": c.get("difficulty"),
                    "participant_count": participant_count,
                    "time_remaining": time_remaining,
                    "status": c.get("status")
                })
                
                if len(results) >= limit:
                    break
            
            return results
            
        except Exception as e:
            print(f"Error getting similar contests: {str(e)}")
            return []
    
    async def get_recent_activity(self, contest_id: str, limit: int = 10) -> List[Dict]:
        """
        Get recent activity feed for a contest.
        
        Includes:
        - New submissions
        - Approved submissions
        - New participants
        - Task completions
        """
        try:
            activities = []
            
            # Get recent submissions (last 24 hours or last 20 activities)
            day_ago = datetime.utcnow() - timedelta(days=1)
            
            submissions = await self.submissions.find({
                "contest_id": contest_id,
                "submitted_at": {"$gte": day_ago}
            }).sort("submitted_at", -1).limit(limit).to_list(length=limit)
            
            for submission in submissions:
                # Get task title
                task = await self.tasks.find_one({"_id": ObjectId(submission["task_id"])})
                task_title = task.get("title") if task else "Unknown Task"
                
                status = submission.get("status")
                
                if status == "approved":
                    activity_type = "approval"
                    message = f"'s submission for '{task_title}' was approved"
                else:
                    activity_type = "submission"
                    message = f" submitted '{task_title}'"
                
                # Convert timestamp to ISO format
                timestamp = submission.get("submitted_at") or submission.get("updated_at")
                if timestamp and hasattr(timestamp, 'isoformat'):
                    timestamp = timestamp.isoformat()
                
                activities.append({
                    "type": activity_type,
                    "user_id": submission.get("user_id"),
                    "username": submission.get("username"),
                    "message": message,
                    "task_title": task_title,
                    "timestamp": timestamp,
                    "status": status
                })
            
            # Get recent participants (joined in last 24h)
            participants = await self.participants.find({
                "contest_id": contest_id,
                "joined_at": {"$gte": day_ago}
            }).sort("joined_at", -1).limit(5).to_list(length=5)
            
            for participant in participants:
                # Convert timestamp to ISO format
                joined_at = participant.get("joined_at")
                if joined_at and hasattr(joined_at, 'isoformat'):
                    joined_at = joined_at.isoformat()
                
                activities.append({
                    "type": "join",
                    "user_id": participant.get("user_id"),
                    "username": participant.get("username"),
                    "message": " joined the contest",
                    "timestamp": joined_at
                })
            
            # Sort all activities by timestamp (most recent first)
            # Convert string timestamps back to datetime for sorting, then back to string
            def parse_timestamp(ts):
                if ts is None:
                    return datetime.min
                if isinstance(ts, str):
                    try:
                        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    except:
                        return datetime.min
                return ts
            
            activities.sort(key=lambda x: parse_timestamp(x.get("timestamp")), reverse=True)
            
            # Format timestamps as "time ago"
            now = datetime.utcnow()
            for activity in activities[:limit]:
                timestamp = activity.get("timestamp")
                if timestamp:
                    delta = now - timestamp
                    
                    if delta.days > 0:
                        activity["time_ago"] = f"{delta.days}d ago"
                    elif delta.seconds >= 3600:
                        hours = delta.seconds // 3600
                        activity["time_ago"] = f"{hours}h ago"
                    elif delta.seconds >= 60:
                        minutes = delta.seconds // 60
                        activity["time_ago"] = f"{minutes}m ago"
                    else:
                        activity["time_ago"] = "just now"
                else:
                    activity["time_ago"] = "recently"
            
            return activities[:limit]
            
        except Exception as e:
            print(f"Error getting recent activity: {str(e)}")
            return []
    
    async def get_top_performers(
        self, 
        contest_id: str, 
        time_period: str = "week",
        limit: int = 5
    ) -> List[Dict]:
        """
        Get top performers in a contest for a specific time period.
        
        time_period: "day", "week", "month", "all_time"
        """
        try:
            # Calculate date filter
            now = datetime.utcnow()
            date_filter = {}
            
            if time_period == "day":
                date_filter = {"$gte": now - timedelta(days=1)}
            elif time_period == "week":
                date_filter = {"$gte": now - timedelta(weeks=1)}
            elif time_period == "month":
                date_filter = {"$gte": now - timedelta(days=30)}
            # "all_time" - no filter
            
            # Get submissions in time period
            query = {"contest_id": contest_id}
            if date_filter:
                query["submitted_at"] = date_filter
            
            submissions = await self.submissions.find(query).to_list(length=None)
            
            # Aggregate by user
            user_stats = {}
            
            for submission in submissions:
                user_id = submission.get("user_id")
                if not user_id:
                    continue
                
                if user_id not in user_stats:
                    user_stats[user_id] = {
                        "user_id": user_id,
                        "username": submission.get("username"),
                        "approved_count": 0,
                        "total_points": 0,
                        "submissions_count": 0
                    }
                
                user_stats[user_id]["submissions_count"] += 1
                
                if submission.get("status") == "approved":
                    user_stats[user_id]["approved_count"] += 1
                    user_stats[user_id]["total_points"] += submission.get("score", 0)
            
            # Sort by approved count, then by points
            top_performers = sorted(
                user_stats.values(),
                key=lambda x: (x["approved_count"], x["total_points"]),
                reverse=True
            )[:limit]
            
            return top_performers
            
        except Exception as e:
            print(f"Error getting top performers: {str(e)}")
            return []
    
    async def get_task_completion_stats(self, contest_id: str) -> List[Dict]:
        """
        Get completion statistics for each task in the contest.
        
        Returns:
        - Task ID and title
        - Total submissions
        - Completion percentage
        - Approval rate
        """
        try:
            # Get all tasks
            tasks = await self.tasks.find({
                "contest_id": contest_id
            }).sort("order", 1).to_list(length=None)
            
            # Get total participants
            total_participants = await self.participants.count_documents({
                "contest_id": contest_id
            })
            
            if total_participants == 0:
                total_participants = 1  # Avoid division by zero
            
            # Get completion stats for each task
            task_stats = []
            
            for task in tasks:
                task_id = str(task["_id"])
                
                # Get all submissions for this task
                submissions = await self.submissions.find({
                    "contest_id": contest_id,
                    "task_id": task_id
                }).to_list(length=None)
                
                # Count unique users who submitted
                unique_submitters = len(set(s.get("user_id") for s in submissions if s.get("user_id")))
                
                # Count approved submissions
                approved_count = sum(1 for s in submissions if s.get("status") == "approved")
                
                # Calculate percentages
                submission_percentage = (unique_submitters / total_participants * 100)
                approval_rate = (approved_count / len(submissions) * 100) if submissions else 0
                
                task_stats.append({
                    "task_id": task_id,
                    "title": task.get("title"),
                    "order": task.get("order", 0),
                    "points": task.get("points", 0),
                    "total_submissions": len(submissions),
                    "unique_submitters": unique_submitters,
                    "approved_count": approved_count,
                    "submission_percentage": round(submission_percentage, 1),
                    "approval_rate": round(approval_rate, 1)
                })
            
            return task_stats
            
        except Exception as e:
            print(f"Error getting task completion stats: {str(e)}")
            return []
