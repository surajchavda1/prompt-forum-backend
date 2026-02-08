from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from bson import ObjectId
from app.models.contest.submission import SubmissionCreate, SubmissionUpdate, SubmissionReview, SubmissionStatus
from app.models.contest.contest import ContestStatus
from app.models.contest.audit import AuditAction
from app.services.contest.audit import AuditService


class SubmissionService:
    """Service for contest submission operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.submissions = db.contest_submissions
        self.tasks = db.contest_tasks
        self.contests = db.contests
        self.participants = db.contest_participants
        self.audit_service = AuditService(db)
    
    def _get_username_lookup_pipeline(self) -> List[Dict]:
        """
        Returns aggregation pipeline stages to lookup user info from users collection.
        Adds 'username', 'full_name', and 'profile_picture' fields to each document.
        """
        return [
            # Convert user_id string to ObjectId for lookup
            {
                "$addFields": {
                    "user_oid": {"$toObjectId": "$user_id"}
                }
            },
            # Lookup user from users collection
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_oid",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            # Extract user fields from user_info array
            {
                "$addFields": {
                    "username": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$user_info.username", 0]},
                            "$username"  # Keep existing if lookup fails
                        ]
                    },
                    "full_name": {
                        "$arrayElemAt": ["$user_info.full_name", 0]
                    },
                    "profile_picture": {
                        "$arrayElemAt": ["$user_info.profile_picture", 0]
                    }
                }
            },
            # Remove temporary fields
            {
                "$project": {
                    "user_oid": 0,
                    "user_info": 0
                }
            }
        ]
    
    async def create_submission(
        self,
        contest_id: str,
        task_id: str,
        user_id: str,
        username: str,
        submission_data: SubmissionCreate,
        attachments: List[dict] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Create a submission for a task"""
        try:
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found", None
            
            # Check if contest is active
            if contest["status"] != ContestStatus.ACTIVE:
                return False, "Contest is not active", None
            
            # Cannot submit to own contest
            if str(contest["owner_id"]) == user_id:
                return False, "Cannot submit to your own contest", None
            
            # Check if user is participant
            participant = await self.participants.find_one({
                "contest_id": contest_id,
                "user_id": user_id
            })
            
            if not participant:
                return False, "Must join contest first", None
            
            # Verify task exists and belongs to contest
            task = await self.tasks.find_one({"_id": ObjectId(task_id)})
            
            if not task or task["contest_id"] != contest_id:
                return False, "Task not found or doesn't belong to this contest", None
            
            # SECURITY: Check if already submitted
            existing = await self.submissions.find_one({
                "task_id": task_id,
                "user_id": user_id
            })
            
            if existing:
                # CRITICAL SECURITY: Block ALL resubmissions
                status = existing["status"]
                
                if status == SubmissionStatus.PENDING:
                    return False, "Already submitted. Please wait for owner review.", None
                
                if status == SubmissionStatus.APPROVED:
                    return False, "Already submitted and approved. Submission is locked.", None
                
                if status == SubmissionStatus.REJECTED:
                    return False, "Submission was rejected and is locked. Cannot resubmit.", None
                
                if status == SubmissionStatus.REVISION_REQUESTED:
                    return False, "Please use the revision endpoint to update your submission.", None
            
            # Create submission with revision tracking
            now = datetime.utcnow()
            submission = {
                "contest_id": contest_id,
                "task_id": task_id,
                "user_id": user_id,
                "username": username,
                "content": submission_data.content,
                "proof_url": submission_data.proof_url,
                "attachments": attachments if attachments else [],
                "status": SubmissionStatus.PENDING,
                "score": None,
                "feedback": None,
                "submitted_at": now,
                "reviewed_at": None,
                "updated_at": now,
                # NEW: Revision system fields
                "version": 1,
                "is_locked": False,
                "can_revise": False,
                "revision_count": 0,
                "first_submitted_at": now,
                "approved_at": None
            }
            
            result = await self.submissions.insert_one(submission)
            submission["_id"] = result.inserted_id
            
            # Update participant's pending count
            await self.participants.update_one(
                {"contest_id": contest_id, "user_id": user_id},
                {"$inc": {"pending_tasks": 1}}
            )
            
            # Log submission to audit trail (SECURITY: Track all submissions)
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.SUBMISSION_CREATED,
                user_id=user_id,
                username=username,
                entity_type="submission",
                entity_id=str(result.inserted_id),
                metadata={
                    "task_id": task_id,
                    "task_title": task.get("title", "Unknown"),
                    "has_proof_url": bool(submission_data.proof_url),
                    "attachment_count": len(attachments) if attachments else 0
                }
            )
            
            return True, "Submission created successfully", submission
            
        except Exception as e:
            return False, f"Failed to create submission: {str(e)}", None
    
    async def get_submission_by_id(self, submission_id: str) -> Optional[Dict]:
        """Get a submission by ID, includes username lookup"""
        try:
            pipeline = [
                {"$match": {"_id": ObjectId(submission_id)}},
                *self._get_username_lookup_pipeline()
            ]
            cursor = self.submissions.aggregate(pipeline)
            submissions = await cursor.to_list(length=1)
            return submissions[0] if submissions else None
        except Exception as e:
            print(f"Error getting submission: {str(e)}")
            return None
    
    async def submit_revision(
        self,
        submission_id: str,
        content: str,
        proof_url: Optional[str],
        attachments: List[dict],
        user_id: str,
        username: str
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Submit a revision after owner requests changes.
        SECURITY:
        - Only if status = revision_requested
        - Only by submission owner
        - Saves old version to revisions collection
        - Increments version number
        - Resets status to pending
        - Locks revision ability until next review
        """
        try:
            submission = await self.submissions.find_one({"_id": ObjectId(submission_id)})
            
            if not submission:
                return False, "Submission not found", None
            
            # SECURITY CHECK 1: Ownership
            if str(submission["user_id"]) != user_id:
                return False, "Can only revise your own submissions", None
            
            # SECURITY CHECK 2: Status must be REVISION_REQUESTED
            if submission["status"] != SubmissionStatus.REVISION_REQUESTED:
                return False, "Revision not allowed. Owner has not requested changes.", None
            
            # SECURITY CHECK 3: Cannot revise if locked
            if submission.get("is_locked", False):
                return False, "Submission is locked and cannot be changed", None
            
            # SECURITY CHECK 4: Must have permission
            if not submission.get("can_revise", False):
                return False, "You do not have permission to revise this submission", None
            
            # Save current version to revisions collection
            current_version = submission.get("version", 1)
            revision = {
                "submission_id": submission_id,
                "contest_id": submission["contest_id"],
                "task_id": submission["task_id"],
                "user_id": submission["user_id"],
                "username": submission["username"],
                "version": current_version,
                "content": submission["content"],
                "proof_url": submission.get("proof_url"),
                "attachments": submission.get("attachments", []),
                "status": submission["status"],
                "feedback": submission.get("feedback"),
                "score": submission.get("score"),
                "reviewed_by": submission.get("reviewed_by"),
                "reviewed_by_name": submission.get("reviewed_by_name"),
                "reviewed_at": submission.get("reviewed_at"),
                "submitted_at": submission.get("updated_at", submission.get("submitted_at")),
                "created_at": datetime.utcnow()
            }
            
            # Insert revision into history
            await self.db.contest_submission_revisions.insert_one(revision)
            
            # Update submission with new version
            new_version = current_version + 1
            now = datetime.utcnow()
            update_data = {
                "content": content,
                "proof_url": proof_url,
                "attachments": attachments,
                "version": new_version,
                "status": SubmissionStatus.PENDING,  # Back to pending for review
                "can_revise": False,  # Lock revision until owner reviews again
                "score": None,  # Reset score
                "feedback": None,  # Clear previous feedback
                "reviewed_at": None,  # Clear review timestamp
                "updated_at": now
            }
            
            await self.submissions.update_one(
                {"_id": ObjectId(submission_id)},
                {
                    "$set": update_data,
                    "$inc": {"revision_count": 1}
                }
            )
            
            # Get updated submission
            updated_submission = await self.submissions.find_one({"_id": ObjectId(submission_id)})
            
            # Log to audit trail
            await self.audit_service.log_action(
                contest_id=submission["contest_id"],
                action=AuditAction.SUBMISSION_CREATED,  # Reuse action or create new one
                user_id=user_id,
                username=username,
                entity_type="submission_revision",
                entity_id=submission_id,
                metadata={
                    "version": new_version,
                    "from_version": current_version,
                    "revision_count": updated_submission.get("revision_count", 0)
                }
            )
            
            return True, f"Revision submitted successfully (Version {new_version})", updated_submission
            
        except Exception as e:
            print(f"Error submitting revision: {str(e)}")
            return False, f"Failed to submit revision: {str(e)}", None
    
    async def update_submission(
        self,
        submission_id: str,
        update_data: SubmissionUpdate,
        user_id: str
    ) -> Tuple[bool, str]:
        """
        Update a submission (only if pending or revision requested).
        SECURITY: Cannot update locked submissions.
        """
        try:
            submission = await self.submissions.find_one({"_id": ObjectId(submission_id)})
            
            if not submission:
                return False, "Submission not found"
            
            # SECURITY CHECK 1: Ownership
            if str(submission["user_id"]) != user_id:
                return False, "Can only edit your own submissions"
            
            # SECURITY CHECK 2: Locked status
            if submission.get("is_locked", False):
                return False, "Submission is locked and cannot be changed"
            
            # SECURITY CHECK 3: Status - can only edit if pending or revision requested
            if submission["status"] not in [SubmissionStatus.PENDING, SubmissionStatus.REVISION_REQUESTED]:
                return False, "Cannot edit approved or rejected submissions"
            
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(submission["contest_id"])})
            
            if not contest:
                return False, "Contest not found"
            
            # Check if contest is still active
            if contest["status"] != ContestStatus.ACTIVE:
                return False, "Contest is no longer active"
            
            # Build update dict
            update_dict = {k: v for k, v in update_data.dict(exclude_none=True).items()}
            
            if not update_dict:
                return False, "No fields to update"
            
            update_dict["updated_at"] = datetime.utcnow()
            update_dict["status"] = SubmissionStatus.PENDING  # Reset to pending after edit
            
            result = await self.submissions.update_one(
                {"_id": ObjectId(submission_id)},
                {"$set": update_dict}
            )
            
            if result.modified_count == 0:
                return False, "No changes made"
            
            return True, "Submission updated successfully"
            
        except Exception as e:
            return False, f"Failed to update: {str(e)}"
    
    async def delete_submission(self, submission_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Delete a submission (only own submission, only if pending).
        SECURITY: Cannot delete locked submissions.
        """
        try:
            submission = await self.submissions.find_one({"_id": ObjectId(submission_id)})
            
            if not submission:
                return False, "Submission not found"
            
            # SECURITY CHECK 1: Ownership
            if str(submission["user_id"]) != user_id:
                return False, "Can only delete your own submissions"
            
            # SECURITY CHECK 2: Locked status
            if submission.get("is_locked", False):
                return False, "Submission is locked and cannot be deleted"
            
            # SECURITY CHECK 3: Status
            if submission["status"] != SubmissionStatus.PENDING:
                return False, "Can only delete pending submissions"
            
            # Delete submission
            await self.submissions.delete_one({"_id": ObjectId(submission_id)})
            
            # Delete any revisions
            await self.db.contest_submission_revisions.delete_many({"submission_id": submission_id})
            
            # Update participant's pending count
            await self.participants.update_one(
                {
                    "contest_id": submission["contest_id"],
                    "user_id": user_id
                },
                {"$inc": {"pending_tasks": -1}}
            )
            
            return True, "Submission deleted successfully"
            
        except Exception as e:
            return False, f"Failed to delete: {str(e)}"
    
    async def review_submission(
        self,
        submission_id: str,
        review_data: SubmissionReview,
        reviewer_id: str,
        reviewer_name: str = "Contest Owner"
    ) -> Tuple[bool, str]:
        """
        Review a submission with immutability and revision control.
        SECURITY:
        - Only contest owner can review
        - Cannot review locked submissions
        - Approved/Rejected = LOCKED forever
        - Revision requested = allows user to revise
        """
        try:
            submission = await self.submissions.find_one({"_id": ObjectId(submission_id)})
            
            if not submission:
                return False, "Submission not found"
            
            # SECURITY CHECK 1: Is submission already locked?
            if submission.get("is_locked", False):
                return False, "Submission is locked. Cannot change approved or rejected status."
            
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(submission["contest_id"])})
            
            if not contest:
                return False, "Contest not found"
            
            # SECURITY CHECK 2: Is reviewer the owner?
            if str(contest["owner_id"]) != reviewer_id:
                return False, "Only contest owner can review submissions"
            
            # Check if contest is active or judging
            if contest["status"] not in [ContestStatus.ACTIVE, ContestStatus.JUDGING]:
                return False, "Cannot review submissions in current contest status"
            
            # SECURITY CHECK 3: Require score for approval
            new_status = review_data.status
            if new_status == SubmissionStatus.APPROVED and not review_data.score:
                return False, "Score (0-100) is required when approving a submission"
            
            # Get old status for audit
            old_status = submission["status"]
            now = datetime.utcnow()
            
            # Prepare update data
            update_data = {
                "status": new_status,
                "score": review_data.score,
                "feedback": review_data.feedback,
                "reviewed_at": now,
                "reviewed_by": reviewer_id,
                "reviewed_by_name": reviewer_name,
                "updated_at": now
            }
            
            # SECURITY: Apply locking rules based on status
            if new_status == SubmissionStatus.APPROVED:
                # LOCK: Approved = immutable forever
                update_data["is_locked"] = True
                update_data["can_revise"] = False
                update_data["approved_at"] = now
                
            elif new_status == SubmissionStatus.REJECTED:
                # LOCK: Rejected = immutable forever
                update_data["is_locked"] = True
                update_data["can_revise"] = False
                
            elif new_status == SubmissionStatus.REVISION_REQUESTED:
                # ALLOW REVISION: User can now resubmit
                update_data["is_locked"] = False
                update_data["can_revise"] = True
            
            # Save current version to revisions before updating
            if submission.get("version", 1) >= 1:
                revision = {
                    "submission_id": submission_id,
                    "contest_id": submission["contest_id"],
                    "task_id": submission["task_id"],
                    "user_id": submission["user_id"],
                    "username": submission["username"],
                    "version": submission.get("version", 1),
                    "content": submission["content"],
                    "proof_url": submission.get("proof_url"),
                    "attachments": submission.get("attachments", []),
                    "status": new_status,  # New status from review
                    "feedback": review_data.feedback,
                    "score": review_data.score,
                    "reviewed_by": reviewer_id,
                    "reviewed_by_name": reviewer_name,
                    "reviewed_at": now,
                    "submitted_at": submission.get("updated_at", submission.get("submitted_at")),
                    "created_at": now
                }
                
                # Insert into revision history
                await self.db.contest_submission_revisions.insert_one(revision)
            
            # Update submission
            await self.submissions.update_one(
                {"_id": ObjectId(submission_id)},
                {"$set": update_data}
            )
            
            # Update participant stats
            user_id = submission["user_id"]
            contest_id = submission["contest_id"]
            
            # If status changed from pending to approved
            points = 0
            if old_status == SubmissionStatus.PENDING and new_status == SubmissionStatus.APPROVED:
                # Get task points
                task = await self.tasks.find_one({"_id": ObjectId(submission["task_id"])})
                points = task["points"] if task else 0
                
                await self.participants.update_one(
                    {"contest_id": contest_id, "user_id": user_id},
                    {
                        "$inc": {
                            "pending_tasks": -1,
                            "approved_tasks": 1,
                            "total_score": points
                        }
                    }
                )
                
                # Update weighted score for prize distribution
                from app.services.contest.scoring import ScoringService
                scoring_service = ScoringService(self.db)
                await scoring_service.update_participant_weighted_score(contest_id, user_id)
            
            # If status changed from approved back to pending/rejected
            elif old_status == SubmissionStatus.APPROVED and new_status != SubmissionStatus.APPROVED:
                task = await self.tasks.find_one({"_id": ObjectId(submission["task_id"])})
                points = task["points"] if task else 0
                
                await self.participants.update_one(
                    {"contest_id": contest_id, "user_id": user_id},
                    {
                        "$inc": {
                            "approved_tasks": -1,
                            "total_score": -points
                        },
                        "$set": {
                            "pending_tasks": 1 if new_status == SubmissionStatus.PENDING else 0
                        }
                    }
                )
                
                # Update weighted score for prize distribution
                from app.services.contest.scoring import ScoringService
                scoring_service = ScoringService(self.db)
                await scoring_service.update_participant_weighted_score(contest_id, user_id)
            
            # Log review to audit trail (SECURITY: Track all approvals/rejections)
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.SUBMISSION_REVIEWED,
                user_id=reviewer_id,
                username=contest.get("owner_name", "Unknown"),
                entity_type="submission",
                entity_id=submission_id,
                changes={
                    "old_status": old_status,
                    "new_status": new_status,
                    "score": review_data.score,
                    "points_change": points if new_status == SubmissionStatus.APPROVED and old_status == SubmissionStatus.PENDING else 0
                },
                metadata={
                    "task_id": submission["task_id"],
                    "participant_id": user_id,
                    "participant_name": submission.get("username", "Unknown"),
                    "feedback_provided": bool(review_data.feedback)
                }
            )
            
            return True, "Submission reviewed successfully"
            
        except Exception as e:
            return False, f"Failed to review: {str(e)}"
    
    async def get_submissions_by_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get submissions for a task, includes username lookup"""
        try:
            match_query = {"task_id": task_id}
            
            if status:
                match_query["status"] = status
            
            skip = (page - 1) * limit
            
            pipeline = [
                {"$match": match_query},
                {"$sort": {"submitted_at": -1}},
                {"$skip": skip},
                {"$limit": limit},
                *self._get_username_lookup_pipeline()
            ]
            
            cursor = self.submissions.aggregate(pipeline)
            submissions = await cursor.to_list(length=limit)
            
            total = await self.submissions.count_documents(match_query)
            
            return submissions, total
            
        except Exception as e:
            print(f"Error getting submissions: {str(e)}")
            return [], 0
    
    async def get_user_submissions(
        self,
        contest_id: str,
        user_id: str
    ) -> List[Dict]:
        """Get all submissions by a user for a contest, includes username and task info"""
        try:
            pipeline = [
                {"$match": {"contest_id": contest_id, "user_id": user_id}},
                {"$sort": {"submitted_at": -1}},
                *self._get_username_lookup_pipeline(),
                # Lookup task info
                {
                    "$addFields": {
                        "task_oid": {"$toObjectId": "$task_id"}
                    }
                },
                {
                    "$lookup": {
                        "from": "contest_tasks",
                        "localField": "task_oid",
                        "foreignField": "_id",
                        "as": "task_info"
                    }
                },
                {
                    "$addFields": {
                        "task_title": {"$ifNull": [{"$arrayElemAt": ["$task_info.title", 0]}, "Unknown"]},
                        "task_points": {"$ifNull": [{"$arrayElemAt": ["$task_info.points", 0]}, 0]}
                    }
                },
                {
                    "$project": {
                        "task_oid": 0,
                        "task_info": 0
                    }
                }
            ]
            
            cursor = self.submissions.aggregate(pipeline)
            return await cursor.to_list(length=None)
            
        except Exception as e:
            print(f"Error getting user submissions: {str(e)}")
            return []
    
    async def get_contest_all_submissions(
        self,
        contest_id: str,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> Tuple[List[Dict], int]:
        """Get all submissions for a contest (owner view), includes username and task info"""
        try:
            match_query = {"contest_id": contest_id}
            
            if status:
                match_query["status"] = status
            
            skip = (page - 1) * limit
            
            pipeline = [
                {"$match": match_query},
                {"$sort": {"submitted_at": -1}},
                {"$skip": skip},
                {"$limit": limit},
                *self._get_username_lookup_pipeline(),
                # Lookup task info
                {
                    "$addFields": {
                        "task_oid": {"$toObjectId": "$task_id"}
                    }
                },
                {
                    "$lookup": {
                        "from": "contest_tasks",
                        "localField": "task_oid",
                        "foreignField": "_id",
                        "as": "task_info"
                    }
                },
                {
                    "$addFields": {
                        "task_title": {"$ifNull": [{"$arrayElemAt": ["$task_info.title", 0]}, "Unknown"]},
                        "task_points": {"$ifNull": [{"$arrayElemAt": ["$task_info.points", 0]}, 0]},
                        "task_order": {"$ifNull": [{"$arrayElemAt": ["$task_info.order", 0]}, 0]}
                    }
                },
                {
                    "$project": {
                        "task_oid": 0,
                        "task_info": 0
                    }
                }
            ]
            
            cursor = self.submissions.aggregate(pipeline)
            submissions = await cursor.to_list(length=limit)
            
            total = await self.submissions.count_documents(match_query)
            
            return submissions, total
            
        except Exception as e:
            print(f"Error getting contest submissions: {str(e)}")
            return [], 0
    
    async def get_submission_history(
        self,
        submission_id: str
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Get full revision history for a submission, includes username lookup.
        Returns: (current_submission, revisions_list)
        """
        try:
            # Get current submission with username lookup
            pipeline = [
                {"$match": {"_id": ObjectId(submission_id)}},
                *self._get_username_lookup_pipeline()
            ]
            cursor = self.submissions.aggregate(pipeline)
            submissions = await cursor.to_list(length=1)
            submission = submissions[0] if submissions else None
            
            if not submission:
                return None, []
            
            # Get all revisions sorted by version
            revisions = await self.db.contest_submission_revisions.find({
                "submission_id": submission_id
            }).sort("version", 1).to_list(length=100)
            
            return submission, revisions
            
        except Exception as e:
            print(f"Error getting submission history: {str(e)}")
            return None, []
