from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from bson import ObjectId
from app.models.contest.contest import ContestStatus, ContestCreate, ContestUpdate
from app.models.contest.audit import AuditAction
from app.services.contest.audit import AuditService
import re


class ContestService:
    """Service for contest operations - inspired by forum post service"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.contests = db.contests
        self.tasks = db.contest_tasks
        self.participants = db.contest_participants
        self.submissions = db.contest_submissions
        self.audit_service = AuditService(db)
    
    def _get_owner_username_lookup_pipeline(self) -> List[Dict]:
        """
        Returns aggregation pipeline stages to lookup owner info from users collection.
        Adds 'username', 'owner_full_name', 'owner_profile_picture' fields and updates 'owner_name'.
        """
        return [
            # Convert owner_id string to ObjectId for lookup
            {
                "$addFields": {
                    "owner_oid": {"$toObjectId": "$owner_id"}
                }
            },
            # Lookup user from users collection
            {
                "$lookup": {
                    "from": "users",
                    "localField": "owner_oid",
                    "foreignField": "_id",
                    "as": "owner_info"
                }
            },
            # Extract user fields from owner_info array
            {
                "$addFields": {
                    "username": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$owner_info.username", 0]},
                            "$owner_name"  # Fallback to stored owner_name
                        ]
                    },
                    "owner_full_name": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$owner_info.full_name", 0]},
                            "$owner_name"  # Fallback to stored owner_name
                        ]
                    },
                    # Override owner_name with current full_name from users collection
                    "owner_name": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$owner_info.full_name", 0]},
                            "$owner_name"  # Keep stored value if lookup fails
                        ]
                    },
                    "owner_profile_picture": {
                        "$arrayElemAt": ["$owner_info.profile_picture", 0]
                    }
                }
            },
            # Remove temporary fields
            {
                "$project": {
                    "owner_oid": 0,
                    "owner_info": 0
                }
            }
        ]
    
    @staticmethod
    def generate_slug(title: str, contest_id: str = None) -> str:
        """Generate URL-friendly slug from title"""
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug.strip('-')
        
        if len(slug) > 100:
            slug = slug[:100].rstrip('-')
        
        if contest_id:
            slug = f"{slug}-{contest_id[:8]}"
        
        return slug
    
    async def is_contest_locked(self, contest_id: str) -> bool:
        """
        Check if contest is locked (cannot be modified).
        Contest is locked if:
        1. Has participants (users joined)
        2. Has payments received (future)
        3. Status is not DRAFT
        
        This prevents owner from changing prize/rules after users commit.
        """
        try:
            # Check if has participants
            participant_count = await self.participants.count_documents({
                "contest_id": contest_id
            })
            
            if participant_count > 0:
                return True  # LOCKED: Users have joined
            
            # Future: Check payment status
            # if contest["payment_received"]:
            #     return True
            
            return False  # Not locked, can still edit
            
        except Exception as e:
            print(f"Error checking lock status: {str(e)}")
            return True  # Fail-safe: lock on error
    
    def _calculate_status(self, start_date: datetime, end_date: datetime, current_status: str) -> str:
        """Calculate contest status based on dates"""
        if current_status == ContestStatus.DRAFT:
            return ContestStatus.DRAFT
        
        now = datetime.utcnow()
        
        if now < start_date:
            return ContestStatus.DRAFT
        elif now >= start_date and now <= end_date:
            return ContestStatus.ACTIVE
        elif now > end_date:
            return ContestStatus.JUDGING
        
        return current_status
    
    def _calculate_time_remaining(self, end_date: datetime) -> Optional[str]:
        """Calculate time remaining"""
        now = datetime.utcnow()
        
        if now >= end_date:
            return None
        
        delta = end_date - now
        days = delta.days
        hours = delta.seconds // 3600
        
        if days > 0:
            return f"{days} days {hours} hours"
        elif hours > 0:
            minutes = (delta.seconds % 3600) // 60
            return f"{hours} hours {minutes} minutes"
        else:
            minutes = delta.seconds // 60
            return f"{minutes} minutes"
    
    def _calculate_time_until_start(self, start_date: datetime) -> Optional[str]:
        """Calculate time until contest starts"""
        now = datetime.utcnow()
        
        if now >= start_date:
            return None
        
        delta = start_date - now
        days = delta.days
        hours = delta.seconds // 3600
        
        if days > 0:
            return f"Starts in {days} days"
        elif hours > 0:
            return f"Starts in {hours} hours"
        else:
            minutes = delta.seconds // 60
            return f"Starts in {minutes} minutes"
    
    async def create_contest(
        self,
        contest_data: ContestCreate,
        owner_id: str,
        owner_name: str,
        cover_image: Optional[str] = None
    ) -> Optional[Dict]:
        """Create a new contest (any user can create)"""
        try:
            contest = {
                "title": contest_data.title,
                "slug": "",  # Will be updated after insert
                "description": contest_data.description,
                "category": contest_data.category,
                "difficulty": contest_data.difficulty,
                "contest_type": contest_data.contest_type,
                "status": ContestStatus.DRAFT,  # Always starts as draft
                "owner_id": owner_id,
                "owner_name": owner_name,
                "total_prize": contest_data.total_prize,
                "max_participants": contest_data.max_participants,
                "start_date": contest_data.start_date,
                "end_date": contest_data.end_date,
                "cover_image": cover_image,
                "rules": contest_data.rules,
                "view_count": 0,
                "upvote_count": 0,
                "downvote_count": 0,
                "upvoters": [],
                "downvoters": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await self.contests.insert_one(contest)
            contest_id = str(result.inserted_id)
            
            # Update slug
            slug = self.generate_slug(contest_data.title, contest_id)
            await self.contests.update_one(
                {"_id": result.inserted_id},
                {"$set": {"slug": slug}}
            )
            
            contest["_id"] = result.inserted_id
            contest["slug"] = slug
            
            # Log creation to audit trail
            await self.audit_service.log_action(
                contest_id=str(result.inserted_id),
                action=AuditAction.CONTEST_CREATED,
                user_id=owner_id,
                username=owner_name,
                entity_type="contest",
                entity_id=str(result.inserted_id),
                metadata={
                    "title": contest_data.title,
                    "prize": contest_data.total_prize,
                    "max_participants": contest_data.max_participants
                }
            )
            
            return contest
            
        except Exception as e:
            print(f"Error creating contest: {str(e)}")
            return None
    
    async def get_contest_by_id(
        self,
        contest_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict]:
        """Get contest by ID with calculated fields, includes owner username"""
        try:
            # Use aggregation to get owner username
            pipeline = [
                {"$match": {"_id": ObjectId(contest_id)}},
                *self._get_owner_username_lookup_pipeline()
            ]
            cursor = self.contests.aggregate(pipeline)
            contests = await cursor.to_list(length=1)
            contest = contests[0] if contests else None
            
            if not contest:
                return None
            
            # Count tasks
            task_count = await self.tasks.count_documents({"contest_id": contest_id})
            
            # Count participants
            participant_count = await self.participants.count_documents({"contest_id": contest_id})
            
            # Count submissions
            submission_count = await self.submissions.count_documents({"contest_id": contest_id})
            
            # Calculate permissions and fields
            is_owner = str(contest["owner_id"]) == user_id if user_id else False
            
            # Check if user joined
            is_joined = False
            if user_id:
                participant = await self.participants.find_one({
                    "contest_id": contest_id,
                    "user_id": user_id
                })
                is_joined = participant is not None
            
            # Can edit/delete only if owner and contest is in DRAFT status
            can_edit = is_owner and contest["status"] == ContestStatus.DRAFT
            can_delete = is_owner and contest["status"] == ContestStatus.DRAFT
            
            # Add calculated fields
            contest["task_count"] = task_count
            contest["current_participants"] = participant_count
            contest["submission_count"] = submission_count
            contest["fill_percentage"] = (participant_count / contest["max_participants"]) * 100
            contest["time_remaining"] = self._calculate_time_remaining(contest["end_date"])
            contest["time_until_start"] = self._calculate_time_until_start(contest["start_date"])
            contest["is_joined"] = is_joined
            contest["is_owner"] = is_owner
            contest["can_edit"] = can_edit
            contest["can_delete"] = can_delete
            
            # Update status if needed
            current_status = self._calculate_status(
                contest["start_date"],
                contest["end_date"],
                contest["status"]
            )
            if current_status != contest["status"] and contest["status"] != ContestStatus.COMPLETED:
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {"status": current_status}}
                )
                contest["status"] = current_status
            
            return contest
            
        except Exception as e:
            print(f"Error getting contest: {str(e)}")
            return None
    
    async def get_contest_by_slug(
        self,
        slug: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict]:
        """Get contest by slug with calculated fields, includes owner username"""
        try:
            # Use aggregation to get owner username
            pipeline = [
                {"$match": {"slug": slug}},
                *self._get_owner_username_lookup_pipeline()
            ]
            cursor = self.contests.aggregate(pipeline)
            contests = await cursor.to_list(length=1)
            contest = contests[0] if contests else None
            
            if not contest:
                return None
            
            contest_id = str(contest["_id"])
            
            # Count tasks
            task_count = await self.tasks.count_documents({"contest_id": contest_id})
            
            # Count participants
            participant_count = await self.participants.count_documents({"contest_id": contest_id})
            
            # Count submissions
            submission_count = await self.submissions.count_documents({"contest_id": contest_id})
            
            # Calculate permissions and fields
            is_owner = str(contest["owner_id"]) == user_id if user_id else False
            
            # Check if user joined
            is_joined = False
            if user_id:
                participant = await self.participants.find_one({
                    "contest_id": contest_id,
                    "user_id": user_id
                })
                is_joined = participant is not None
            
            # Can edit/delete only if owner and contest is in DRAFT status
            can_edit = is_owner and contest["status"] == ContestStatus.DRAFT
            can_delete = is_owner and contest["status"] == ContestStatus.DRAFT
            
            # Add calculated fields
            contest["task_count"] = task_count
            contest["current_participants"] = participant_count
            contest["submission_count"] = submission_count
            contest["fill_percentage"] = (participant_count / contest["max_participants"]) * 100
            contest["time_remaining"] = self._calculate_time_remaining(contest["end_date"])
            contest["time_until_start"] = self._calculate_time_until_start(contest["start_date"])
            contest["is_joined"] = is_joined
            contest["is_owner"] = is_owner
            contest["can_edit"] = can_edit
            contest["can_delete"] = can_delete
            
            # Update status if needed
            current_status = self._calculate_status(
                contest["start_date"],
                contest["end_date"],
                contest["status"]
            )
            if current_status != contest["status"] and contest["status"] != ContestStatus.COMPLETED:
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {"status": current_status}}
                )
                contest["status"] = current_status
            
            return contest
            
        except Exception as e:
            print(f"Error getting contest by slug: {str(e)}")
            return None
    
    async def get_contests(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        owner_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        user_id: Optional[str] = None
    ) -> Tuple[List[Dict], int]:
        """Get contests with filtering, includes owner username"""
        try:
            match_query = {}
            
            if status:
                # Convert enum to string value if needed
                match_query["status"] = status.value if hasattr(status, 'value') else status
            if category:
                match_query["category"] = category
            if difficulty:
                # Convert enum to string value if needed
                match_query["difficulty"] = difficulty.value if hasattr(difficulty, 'value') else difficulty
            if owner_id:
                # If specific owner_id requested, use it
                match_query["owner_id"] = owner_id
            else:
                # Otherwise, filter out old contests without owner_id
                match_query["owner_id"] = {"$exists": True}
            
            skip = (page - 1) * limit
            
            # Use aggregation to get owner username
            pipeline = [
                {"$match": match_query},
                {"$sort": {"created_at": -1}},
                {"$skip": skip},
                {"$limit": limit},
                *self._get_owner_username_lookup_pipeline()
            ]
            
            cursor = self.contests.aggregate(pipeline)
            contests = await cursor.to_list(length=limit)
            
            total = await self.contests.count_documents(match_query)
            
            # Add calculated fields for each contest
            for contest in contests:
                contest_id = str(contest["_id"])
                
                # Count tasks, participants, submissions
                task_count = await self.tasks.count_documents({"contest_id": contest_id})
                participant_count = await self.participants.count_documents({"contest_id": contest_id})
                submission_count = await self.submissions.count_documents({"contest_id": contest_id})
                
                contest["task_count"] = task_count
                contest["current_participants"] = participant_count
                contest["submission_count"] = submission_count
                contest["fill_percentage"] = (participant_count / contest.get("max_participants", 100)) * 100
                contest["time_remaining"] = self._calculate_time_remaining(contest["end_date"])
                contest["time_until_start"] = self._calculate_time_until_start(contest["start_date"])
                
                # Check if user joined
                is_joined = False
                is_owner = str(contest["owner_id"]) == user_id if user_id else False
                
                if user_id:
                    participant = await self.participants.find_one({
                        "contest_id": contest_id,
                        "user_id": user_id
                    })
                    is_joined = participant is not None
                
                contest["is_joined"] = is_joined
                contest["is_owner"] = is_owner
                contest["can_edit"] = is_owner and contest["status"] == ContestStatus.DRAFT
                contest["can_delete"] = is_owner and contest["status"] == ContestStatus.DRAFT
            
            return contests, total
            
        except Exception as e:
            print(f"Error getting contests: {str(e)}")
            return [], 0
    
    async def update_contest(
        self,
        contest_id: str,
        update_data: ContestUpdate,
        user_id: str
    ) -> Tuple[bool, str]:
        """Update contest (only owner, only in DRAFT status)"""
        try:
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can edit"
            
            # Check status - can only edit in DRAFT
            if contest["status"] != ContestStatus.DRAFT:
                return False, "Cannot edit contest after it has started"
            
            # SECURITY: Check if contest is locked (has participants)
            is_locked = await self.is_contest_locked(contest_id)
            
            # Build update dict
            update_dict = {k: v for k, v in update_data.dict(exclude_none=True).items()}
            
            if not update_dict:
                return False, "No fields to update"
            
            # SECURITY: If contest is locked, restrict critical financial fields
            if is_locked:
                # Fields that CANNOT be changed after users join
                restricted_fields = ["total_prize", "max_participants", "start_date", "end_date"]
                
                for field in restricted_fields:
                    if field in update_dict:
                        return False, f"Cannot change {field} after participants have joined. This protects participants from fraud."
                
                # Only allow non-critical updates (description, rules)
                allowed_fields = ["description", "rules"]
                update_dict = {k: v for k, v in update_dict.items() if k in allowed_fields}
                
                if not update_dict:
                    return False, "No updatable fields provided. Critical fields locked after users join."
            
            update_dict["updated_at"] = datetime.utcnow()
            
            # Update slug if title changed (only if not locked)
            if "title" in update_dict and not is_locked:
                update_dict["slug"] = self.generate_slug(update_dict["title"], contest_id)
            
            # Log changes to audit trail
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.CONTEST_UPDATED,
                user_id=user_id,
                username=contest.get("owner_name", "Unknown"),
                entity_type="contest",
                entity_id=contest_id,
                changes=update_dict,
                metadata={"is_locked": is_locked}
            )
            
            result = await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": update_dict}
            )
            
            if result.modified_count == 0:
                return False, "No changes made"
            
            return True, "Contest updated successfully"
            
        except Exception as e:
            return False, f"Failed to update: {str(e)}"
    
    async def delete_contest(self, contest_id: str, user_id: str) -> Tuple[bool, str]:
        """Delete a contest (only owner, only in DRAFT status)"""
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can delete"
            
            # Check status
            if contest["status"] != ContestStatus.DRAFT:
                return False, "Cannot delete contest after it has started"
            
            # Check if has participants
            participant_count = await self.participants.count_documents({"contest_id": contest_id})
            if participant_count > 0:
                return False, "Cannot delete contest with participants"
            
            # Delete contest and its tasks
            await self.contests.delete_one({"_id": ObjectId(contest_id)})
            await self.tasks.delete_many({"contest_id": contest_id})
            
            return True, "Contest deleted successfully"
            
        except Exception as e:
            return False, f"Failed to delete: {str(e)}"
    
    async def start_contest(self, contest_id: str, user_id: str) -> Tuple[bool, str]:
        """Start a contest (change status from DRAFT to ACTIVE)"""
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can start"
            
            # Check status
            if contest["status"] != ContestStatus.DRAFT:
                return False, "Contest already started"
            
            # Check if has tasks
            task_count = await self.tasks.count_documents({"contest_id": contest_id})
            if task_count == 0:
                return False, "Cannot start contest without tasks"
            
            # Check if start date is in the future
            now = datetime.utcnow()
            if contest["start_date"] > now:
                # Update start_date to now if it's in the future
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {
                        "start_date": now,
                        "status": ContestStatus.ACTIVE,
                        "updated_at": now
                    }}
                )
            else:
                # Just update status
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {
                        "status": ContestStatus.ACTIVE,
                        "updated_at": now
                    }}
                )
            
            # Log start to audit trail (SECURITY: Proves when contest became active)
            participant_count = await self.participants.count_documents({"contest_id": contest_id})
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.CONTEST_STARTED,
                user_id=user_id,
                username=contest.get("owner_name", "Unknown"),
                entity_type="contest",
                entity_id=contest_id,
                metadata={
                    "participant_count": participant_count,
                    "task_count": task_count,
                    "prize_amount": contest.get("total_prize", 0),
                    "locked_at": now.isoformat()
                }
            )
            
            return True, "Contest started successfully"
            
        except Exception as e:
            return False, f"Failed to start: {str(e)}"
    
    async def complete_contest(self, contest_id: str, user_id: str) -> Tuple[bool, str]:
        """Complete a contest (change status to COMPLETED)"""
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can complete"
            
            # Check status
            if contest["status"] not in [ContestStatus.ACTIVE, ContestStatus.JUDGING]:
                return False, "Contest must be active or judging"
            
            # Update status
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": {
                    "status": ContestStatus.COMPLETED,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            return True, "Contest completed successfully"
            
        except Exception as e:
            return False, f"Failed to complete: {str(e)}"
    
    async def join_contest(
        self,
        contest_id: str,
        user_id: str,
        username: str
    ) -> Tuple[bool, str]:
        """User joins a contest"""
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Cannot join own contest
            if str(contest["owner_id"]) == user_id:
                return False, "Cannot join your own contest"
            
            # Check status
            if contest["status"] not in [ContestStatus.DRAFT, ContestStatus.ACTIVE]:
                return False, "Contest registration closed"
            
            # Check if already joined
            existing = await self.participants.find_one({
                "contest_id": contest_id,
                "user_id": user_id
            })
            if existing:
                return False, "Already joined this contest"
            
            # Check capacity
            participant_count = await self.participants.count_documents({"contest_id": contest_id})
            if participant_count >= contest["max_participants"]:
                return False, "Contest is full"
            
            # Add participant
            participant = {
                "contest_id": contest_id,
                "user_id": user_id,
                "username": username,
                "joined_at": datetime.utcnow(),
                "total_score": 0,
                "approved_tasks": 0,
                "pending_tasks": 0,
                "earnings": 0.0
            }
            
            await self.participants.insert_one(participant)
            
            # Log join to audit trail (SECURITY: Track all participants)
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.USER_JOINED,
                user_id=user_id,
                username=username,
                entity_type="participant",
                entity_id=str(participant["_id"]) if "_id" in participant else None,
                metadata={
                    "participant_number": participant_count + 1,
                    "max_participants": contest["max_participants"],
                    "fill_percentage": ((participant_count + 1) / contest["max_participants"]) * 100
                }
            )
            
            return True, "Successfully joined contest"
            
        except Exception as e:
            print(f"Error joining contest: {str(e)}")
            return False, f"Failed to join: {str(e)}"
    
    async def leave_contest(self, contest_id: str, user_id: str) -> Tuple[bool, str]:
        """Leave a contest (only if contest hasn't started)"""
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Can only leave if contest is in DRAFT
            if contest["status"] != ContestStatus.DRAFT:
                return False, "Cannot leave after contest has started"
            
            # Check if joined
            participant = await self.participants.find_one({
                "contest_id": contest_id,
                "user_id": user_id
            })
            
            if not participant:
                return False, "Not a participant"
            
            # Check if has submissions
            submission_count = await self.submissions.count_documents({
                "contest_id": contest_id,
                "user_id": user_id
            })
            
            if submission_count > 0:
                return False, "Cannot leave after submitting"
            
            # Remove participant
            await self.participants.delete_one({
                "contest_id": contest_id,
                "user_id": user_id
            })
            
            return True, "Left contest successfully"
            
        except Exception as e:
            return False, f"Failed to leave: {str(e)}"
    
    async def increment_view_count(self, contest_id: str) -> bool:
        """Increment contest view count"""
        try:
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$inc": {"view_count": 1}}
            )
            return True
        except:
            return False
    
    async def vote_contest(
        self,
        contest_id: str,
        user_id: str,
        vote_type: str
    ) -> Tuple[bool, str, Optional[int]]:
        """Vote on a contest (upvote/downvote)"""
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found", None
            
            # Cannot vote on own contest
            if contest["owner_id"] == user_id:
                return False, "Cannot vote on your own contest", None
            
            upvoters = contest.get("upvoters", [])
            downvoters = contest.get("downvoters", [])
            
            # Remove from both lists first
            if user_id in upvoters:
                upvoters.remove(user_id)
            if user_id in downvoters:
                downvoters.remove(user_id)
            
            # Add to appropriate list
            if vote_type == "upvote":
                upvoters.append(user_id)
            elif vote_type == "downvote":
                downvoters.append(user_id)
            elif vote_type == "remove":
                pass  # Already removed above
            else:
                return False, "Invalid vote type", None
            
            # Update contest
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": {
                    "upvoters": upvoters,
                    "downvoters": downvoters,
                    "upvote_count": len(upvoters),
                    "downvote_count": len(downvoters),
                    "updated_at": datetime.utcnow()
                }}
            )
            
            return True, "Vote recorded", len(upvoters) - len(downvoters)
            
        except Exception as e:
            return False, f"Failed to vote: {str(e)}", None
