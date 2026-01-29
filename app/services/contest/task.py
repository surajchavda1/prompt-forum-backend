from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from bson import ObjectId
from app.models.contest.task import TaskCreate, TaskUpdate
from app.models.contest.contest import ContestStatus


class TaskService:
    """Service for contest task operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tasks = db.contest_tasks
        self.contests = db.contests
        self.submissions = db.contest_submissions
    
    async def create_task(
        self,
        contest_id: str,
        task_data: TaskCreate,
        user_id: str
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Create a task for a contest (only owner, only in DRAFT)"""
        try:
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found", None
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can add tasks", None
            
            # Check status - can only add tasks in DRAFT
            if contest["status"] != ContestStatus.DRAFT:
                return False, "Cannot add tasks after contest has started", None
            
            # Create task
            task = {
                "contest_id": contest_id,
                "title": task_data.title,
                "description": task_data.description,
                "points": task_data.points,
                "order": task_data.order,
                "requirements": task_data.requirements,
                "deliverables": task_data.deliverables,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await self.tasks.insert_one(task)
            task["_id"] = result.inserted_id
            
            return True, "Task created successfully", task
            
        except Exception as e:
            return False, f"Failed to create task: {str(e)}", None
    
    async def get_task_by_id(self, task_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Get task by ID with user submission status"""
        try:
            task = await self.tasks.find_one({"_id": ObjectId(task_id)})
            
            if not task:
                return None
            
            task_id_str = str(task["_id"])
            contest_id = task["contest_id"]
            
            # Count submissions for this task
            submission_count = await self.submissions.count_documents({
                "task_id": task_id_str
            })
            
            approved_count = await self.submissions.count_documents({
                "task_id": task_id_str,
                "status": "approved"
            })
            
            # Check if user submitted
            user_submitted = False
            user_approved = False
            
            if user_id:
                user_submission = await self.submissions.find_one({
                    "task_id": task_id_str,
                    "user_id": user_id
                })
                user_submitted = user_submission is not None
                user_approved = user_submission and user_submission.get("status") == "approved"
            
            task["submission_count"] = submission_count
            task["approved_count"] = approved_count
            task["user_submitted"] = user_submitted
            task["user_approved"] = user_approved
            
            return task
            
        except Exception as e:
            print(f"Error getting task: {str(e)}")
            return None
    
    async def get_contest_tasks(
        self,
        contest_id: str,
        user_id: Optional[str] = None
    ) -> List[Dict]:
        """Get all tasks for a contest"""
        try:
            tasks = await self.tasks.find({
                "contest_id": contest_id
            }).sort("order", 1).to_list(length=None)
            
            # Add submission info for each task
            for task in tasks:
                task_id = str(task["_id"])
                
                submission_count = await self.submissions.count_documents({"task_id": task_id})
                approved_count = await self.submissions.count_documents({
                    "task_id": task_id,
                    "status": "approved"
                })
                
                task["submission_count"] = submission_count
                task["approved_count"] = approved_count
                
                # Check user's submission status
                if user_id:
                    user_submission = await self.submissions.find_one({
                        "task_id": task_id,
                        "user_id": user_id
                    })
                    task["user_submitted"] = user_submission is not None
                    task["user_approved"] = user_submission and user_submission.get("status") == "approved"
                else:
                    task["user_submitted"] = False
                    task["user_approved"] = False
            
            return tasks
            
        except Exception as e:
            print(f"Error getting tasks: {str(e)}")
            return []
    
    async def update_task(
        self,
        task_id: str,
        update_data: TaskUpdate,
        user_id: str
    ) -> Tuple[bool, str]:
        """Update a task (only owner, only before contest starts)"""
        try:
            task = await self.tasks.find_one({"_id": ObjectId(task_id)})
            
            if not task:
                return False, "Task not found"
            
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(task["contest_id"])})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can edit tasks"
            
            # Check status
            if contest["status"] != ContestStatus.DRAFT:
                return False, "Cannot edit tasks after contest has started"
            
            # Build update dict
            update_dict = {k: v for k, v in update_data.dict(exclude_none=True).items()}
            
            if not update_dict:
                return False, "No fields to update"
            
            update_dict["updated_at"] = datetime.utcnow()
            
            result = await self.tasks.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_dict}
            )
            
            if result.modified_count == 0:
                return False, "No changes made"
            
            return True, "Task updated successfully"
            
        except Exception as e:
            return False, f"Failed to update: {str(e)}"
    
    async def delete_task(self, task_id: str, user_id: str) -> Tuple[bool, str]:
        """Delete a task (only owner, only before contest starts)"""
        try:
            task = await self.tasks.find_one({"_id": ObjectId(task_id)})
            
            if not task:
                return False, "Task not found"
            
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(task["contest_id"])})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can delete tasks"
            
            # Check status
            if contest["status"] != ContestStatus.DRAFT:
                return False, "Cannot delete tasks after contest has started"
            
            # Check if has submissions
            submission_count = await self.submissions.count_documents({
                "task_id": str(task["_id"])
            })
            
            if submission_count > 0:
                return False, "Cannot delete task with submissions"
            
            # Delete task
            await self.tasks.delete_one({"_id": ObjectId(task_id)})
            
            return True, "Task deleted successfully"
            
        except Exception as e:
            return False, f"Failed to delete: {str(e)}"
