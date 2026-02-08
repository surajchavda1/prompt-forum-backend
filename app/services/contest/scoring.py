"""
Contest Scoring Service - Weighted Score Calculation

Implements the weighted scoring system:
- Task Weightage = Task Points / Sum of All Task Points
- Participant Task Score = Submission Score (0-100) × Task Weightage
- Final Score = Sum of All Weighted Task Scores

This ensures fair and transparent scoring based on task importance.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from bson import ObjectId
from app.models.contest.submission import SubmissionStatus


class ScoringService:
    """
    Service for weighted score calculations in contests.
    
    Scoring Formula:
    1. Task Weightage = Task Points / Total Points of All Tasks
    2. Weighted Score = Submission Score (0-100) × Task Weightage
    3. Final Score = Sum of all Weighted Scores
    
    Example:
    - Task 1: 90 points, Score: 100 -> 100 × (90/143) = 62.94
    - Task 2: 23 points, Score: 80  -> 80 × (23/143) = 12.87
    - Task 3: 30 points, Score: 60  -> 60 × (30/143) = 12.59
    - Final Score: 88.39
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.contests = db.contests
        self.tasks = db.contest_tasks
        self.submissions = db.contest_submissions
        self.participants = db.contest_participants
    
    async def get_task_weightages(self, contest_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Calculate weightage for each task based on points.
        
        Returns:
        {
            "task_id": {
                "title": str,
                "points": int,
                "weightage": float (0-1, sum = 1)
            }
        }
        """
        # Get all tasks for the contest
        tasks = await self.tasks.find({"contest_id": contest_id}).to_list(length=None)
        
        if not tasks:
            return {}
        
        # Calculate total points
        total_points = sum(task.get("points", 0) for task in tasks)
        
        if total_points == 0:
            return {}
        
        # Calculate weightage for each task
        weightages = {}
        for task in tasks:
            task_id = str(task["_id"])
            points = task.get("points", 0)
            weightage = points / total_points
            
            weightages[task_id] = {
                "title": task.get("title", "Unknown"),
                "points": points,
                "weightage": round(weightage, 10)  # High precision for accuracy
            }
        
        return weightages
    
    async def calculate_participant_weighted_score(
        self,
        contest_id: str,
        user_id: str
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calculate weighted score for a single participant.
        
        Only counts APPROVED submissions with scores.
        
        Returns:
        (weighted_score, task_scores_list)
        
        task_scores_list: [
            {
                "task_id": str,
                "task_title": str,
                "points": int,
                "weightage": float,
                "submission_score": int (0-100),
                "weighted_score": float
            }
        ]
        """
        # Get task weightages
        weightages = await self.get_task_weightages(contest_id)
        
        if not weightages:
            return 0.0, []
        
        # Get all approved submissions for this user in this contest
        submissions = await self.submissions.find({
            "contest_id": contest_id,
            "user_id": user_id,
            "status": SubmissionStatus.APPROVED,
            "score": {"$exists": True, "$ne": None}
        }).to_list(length=None)
        
        task_scores = []
        total_weighted_score = 0.0
        
        for submission in submissions:
            task_id = submission.get("task_id")
            submission_score = submission.get("score", 0)
            
            if task_id not in weightages:
                continue
            
            task_info = weightages[task_id]
            weightage = task_info["weightage"]
            
            # Calculate weighted score for this task
            weighted_score = submission_score * weightage
            
            task_scores.append({
                "task_id": task_id,
                "task_title": task_info["title"],
                "points": task_info["points"],
                "weightage": weightage,
                "submission_score": submission_score,
                "weighted_score": round(weighted_score, 10)
            })
            
            total_weighted_score += weighted_score
        
        return round(total_weighted_score, 10), task_scores
    
    async def calculate_all_participant_scores(
        self,
        contest_id: str
    ) -> List[Dict[str, Any]]:
        """
        Calculate and rank all participants by weighted score.
        
        Returns sorted list (highest score first):
        [
            {
                "user_id": str,
                "username": str,
                "weighted_score": float,
                "task_scores": List[Dict],
                "rank": int,
                "approved_tasks": int,
                "total_tasks": int
            }
        ]
        """
        # Get all participants
        participants = await self.participants.find({
            "contest_id": contest_id
        }).to_list(length=None)
        
        if not participants:
            return []
        
        # Get task weightages
        weightages = await self.get_task_weightages(contest_id)
        total_tasks = len(weightages)
        
        # Calculate scores for each participant
        scored_participants = []
        
        for participant in participants:
            user_id = participant["user_id"]
            username = participant.get("username", "Unknown")
            
            weighted_score, task_scores = await self.calculate_participant_weighted_score(
                contest_id, user_id
            )
            
            scored_participants.append({
                "user_id": user_id,
                "username": username,
                "weighted_score": weighted_score,
                "task_scores": task_scores,
                "approved_tasks": len(task_scores),
                "total_tasks": total_tasks
            })
        
        # Sort by weighted score (descending)
        scored_participants.sort(key=lambda x: x["weighted_score"], reverse=True)
        
        # Add rank
        for idx, participant in enumerate(scored_participants, 1):
            participant["rank"] = idx
        
        return scored_participants
    
    async def update_participant_weighted_score(
        self,
        contest_id: str,
        user_id: str
    ) -> Tuple[bool, float]:
        """
        Recalculate and update a participant's weighted score in the database.
        
        Call this after a submission is approved/rejected.
        
        Returns: (success, new_weighted_score)
        """
        try:
            weighted_score, task_scores = await self.calculate_participant_weighted_score(
                contest_id, user_id
            )
            
            # Update participant record
            result = await self.participants.update_one(
                {"contest_id": contest_id, "user_id": user_id},
                {
                    "$set": {
                        "weighted_score": weighted_score,
                        "task_scores": task_scores,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count > 0 or result.matched_count > 0, weighted_score
            
        except Exception as e:
            print(f"Error updating participant weighted score: {str(e)}")
            return False, 0.0
    
    async def update_all_participant_scores(self, contest_id: str) -> int:
        """
        Recalculate weighted scores for all participants in a contest.
        
        Call this before prize distribution or when bulk recalculation needed.
        
        Returns: Number of participants updated
        """
        participants = await self.participants.find({
            "contest_id": contest_id
        }).to_list(length=None)
        
        updated_count = 0
        
        for participant in participants:
            success, _ = await self.update_participant_weighted_score(
                contest_id, participant["user_id"]
            )
            if success:
                updated_count += 1
        
        return updated_count
    
    async def get_winners(
        self,
        contest_id: str,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Get ranked winners with scores > min_score.
        
        Returns:
        [
            {
                "user_id": str,
                "username": str,
                "rank": int,
                "weighted_score": float,
                "approved_tasks": int,
                "task_scores": List[Dict]
            }
        ]
        """
        scored_participants = await self.calculate_all_participant_scores(contest_id)
        
        # Filter by minimum score
        winners = [
            p for p in scored_participants
            if p["weighted_score"] > min_score
        ]
        
        return winners
    
    async def calculate_prize_shares(
        self,
        contest_id: str,
        prize_pool: float
    ) -> List[Dict[str, Any]]:
        """
        Calculate prize share for each winner based on weighted scores.
        
        Formula: Prize Share = (Participant Score / Total Scores) × Prize Pool
        
        Returns:
        [
            {
                "user_id": str,
                "username": str,
                "rank": int,
                "weighted_score": float,
                "score_percentage": float,
                "prize_amount": float
            }
        ]
        """
        # Get winners with score > 0
        winners = await self.get_winners(contest_id, min_score=0.0)
        
        if not winners:
            return []
        
        # Calculate total score
        total_score = sum(w["weighted_score"] for w in winners)
        
        if total_score == 0:
            return []
        
        # Calculate prize share for each winner
        prize_shares = []
        
        for winner in winners:
            score_percentage = (winner["weighted_score"] / total_score) * 100
            prize_amount = (winner["weighted_score"] / total_score) * prize_pool
            
            prize_shares.append({
                "user_id": winner["user_id"],
                "username": winner["username"],
                "rank": winner["rank"],
                "weighted_score": winner["weighted_score"],
                "score_percentage": round(score_percentage, 2),
                "prize_amount": round(prize_amount, 2)
            })
        
        return prize_shares
    
    async def get_leaderboard(
        self,
        contest_id: str,
        page: int = 1,
        limit: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated leaderboard sorted by weighted score.
        
        Returns: (leaderboard_entries, total_count)
        """
        # Get all scored participants
        scored_participants = await self.calculate_all_participant_scores(contest_id)
        total = len(scored_participants)
        
        # Paginate
        start = (page - 1) * limit
        end = start + limit
        
        leaderboard = scored_participants[start:end]
        
        return leaderboard, total
    
    async def get_task_wise_winners(
        self,
        contest_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get winners for each task based on submission scores.
        
        Returns list of tasks with their top performers:
        [
            {
                "task_id": str,
                "task_title": str,
                "task_points": int,
                "task_weightage": float,
                "total_submissions": int,
                "approved_submissions": int,
                "winners": [
                    {
                        "rank": int,
                        "user_id": str,
                        "username": str,
                        "submission_score": int (0-100),
                        "weighted_score": float,
                        "submitted_at": datetime,
                        "approved_at": datetime
                    }
                ]
            }
        ]
        """
        from app.models.contest.submission import SubmissionStatus
        
        # Get all tasks for the contest
        tasks = await self.tasks.find({"contest_id": contest_id}).sort("order", 1).to_list(length=None)
        
        if not tasks:
            return []
        
        # Get task weightages
        weightages = await self.get_task_weightages(contest_id)
        
        task_winners = []
        
        for task in tasks:
            task_id = str(task["_id"])
            task_info = weightages.get(task_id, {})
            
            # Get all submissions for this task
            total_submissions = await self.submissions.count_documents({
                "contest_id": contest_id,
                "task_id": task_id
            })
            
            # Get approved submissions sorted by score (highest first)
            approved_submissions = await self.submissions.find({
                "contest_id": contest_id,
                "task_id": task_id,
                "status": SubmissionStatus.APPROVED.value,
                "score": {"$exists": True, "$ne": None}
            }).sort("score", -1).to_list(length=None)
            
            # Build winners list for this task
            winners = []
            for idx, submission in enumerate(approved_submissions, 1):
                weightage = task_info.get("weightage", 0)
                submission_score = submission.get("score", 0)
                weighted_score = submission_score * weightage
                
                # Lookup username from participants or use stored username
                participant = await self.participants.find_one({
                    "contest_id": contest_id,
                    "user_id": submission["user_id"]
                })
                
                # Safely get username
                username = "Unknown"
                if participant:
                    username = participant.get("username", "Unknown")
                elif submission.get("username"):
                    username = submission.get("username")
                
                winners.append({
                    "rank": idx,
                    "user_id": submission["user_id"],
                    "username": username,
                    "submission_score": submission_score,
                    "weighted_score": round(weighted_score, 4),
                    "submitted_at": submission.get("submitted_at"),
                    "approved_at": submission.get("approved_at")
                })
            
            task_winners.append({
                "task_id": task_id,
                "task_title": task.get("title", "Unknown"),
                "task_points": task.get("points", 0),
                "task_weightage": round(task_info.get("weightage", 0), 4),
                "total_submissions": total_submissions,
                "approved_submissions": len(approved_submissions),
                "winners": winners,
                "top_winner": winners[0] if winners else None
            })
        
        return task_winners
    
    async def get_task_leaderboard(
        self,
        contest_id: str,
        task_id: str,
        page: int = 1,
        limit: int = 50
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
        """
        Get leaderboard for a specific task.
        
        Returns: (leaderboard_entries, total_count, task_info)
        """
        from app.models.contest.submission import SubmissionStatus
        
        # Get task info
        task = await self.tasks.find_one({"_id": ObjectId(task_id)})
        if not task:
            return [], 0, {}
        
        # Get task weightage
        weightages = await self.get_task_weightages(contest_id)
        task_info = weightages.get(task_id, {})
        
        # Get approved submissions for this task
        skip = (page - 1) * limit
        
        submissions = await self.submissions.find({
            "contest_id": contest_id,
            "task_id": task_id,
            "status": SubmissionStatus.APPROVED.value,
            "score": {"$exists": True, "$ne": None}
        }).sort("score", -1).skip(skip).limit(limit).to_list(length=limit)
        
        total = await self.submissions.count_documents({
            "contest_id": contest_id,
            "task_id": task_id,
            "status": SubmissionStatus.APPROVED.value
        })
        
        # Build leaderboard
        leaderboard = []
        weightage = task_info.get("weightage", 0)
        
        for idx, submission in enumerate(submissions, start=skip + 1):
            submission_score = submission.get("score", 0)
            weighted_score = submission_score * weightage
            
            # Lookup username
            participant = await self.participants.find_one({
                "contest_id": contest_id,
                "user_id": submission["user_id"]
            })
            
            # Safely get username
            username = "Unknown"
            if participant:
                username = participant.get("username", "Unknown")
            elif submission.get("username"):
                username = submission.get("username")
            
            leaderboard.append({
                "rank": idx,
                "user_id": submission["user_id"],
                "username": username,
                "submission_score": submission_score,
                "weighted_score": round(weighted_score, 4),
                "feedback": submission.get("feedback"),
                "submitted_at": submission.get("submitted_at"),
                "approved_at": submission.get("approved_at")
            })
        
        task_details = {
            "task_id": task_id,
            "task_title": task.get("title", "Unknown"),
            "task_points": task.get("points", 0),
            "task_weightage": round(weightage, 4),
            "total_approved": total
        }
        
        return leaderboard, total, task_details
