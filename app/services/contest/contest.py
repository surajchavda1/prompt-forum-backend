from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from bson import ObjectId
from app.models.contest.contest import ContestStatus, ContestCreate, ContestUpdate
from app.models.contest.audit import AuditAction
from app.services.contest.audit import AuditService
from app.utils.wallet import WalletUtils
from app.models.payment.transaction import TransactionCategory
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
                # New category/subcategory/tags structure
                "category_id": contest_data.category_id,
                "subcategory_id": contest_data.subcategory_id,
                "tags": contest_data.tags or [],
                # Legacy category field for backward compatibility
                "category": contest_data.category or "",
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
                # Visibility & Lifecycle
                "is_active": False,  # Not visible until published
                "published_at": None,
                "completed_at": None,
                "cancelled_at": None,
                "auto_completed": False,
                "grace_period_hours": 24,
                # Voting
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
            
            # Calculate permissions based on state and participants
            can_edit = is_owner and contest["status"] == ContestStatus.DRAFT and participant_count == 0
            can_delete = is_owner and contest["status"] == ContestStatus.DRAFT and participant_count == 0
            can_publish = is_owner and contest["status"] == ContestStatus.DRAFT and task_count > 0
            can_cancel = is_owner and contest["status"] in [ContestStatus.DRAFT, ContestStatus.UPCOMING] and participant_count == 0
            
            # Can complete only if has participants, submissions, and approved submissions
            approved_count = await self.submissions.count_documents({
                "contest_id": contest_id,
                "status": "approved"
            })
            can_complete = (
                is_owner and 
                contest["status"] in [ContestStatus.ACTIVE, ContestStatus.JUDGING] and
                participant_count > 0 and
                submission_count > 0 and
                approved_count > 0
            )
            
            # Can join: not owner, not joined, status is UPCOMING/ACTIVE, not full, end_date not passed, not completed
            now = datetime.utcnow()
            end_date = contest.get("end_date")
            is_ended = end_date and end_date < now
            is_full = participant_count >= contest["max_participants"]
            is_completed = (
                contest["status"] == ContestStatus.COMPLETED or
                contest.get("prizes_distributed", False) or
                contest.get("refund_processed", False)
            )
            can_join = (
                not is_owner and
                not is_joined and
                contest["status"] in [ContestStatus.UPCOMING, ContestStatus.ACTIVE] and
                contest.get("is_active", False) and
                not is_full and
                not is_ended and
                not is_completed
            )
            
            # Add calculated fields
            contest["task_count"] = task_count
            contest["current_participants"] = participant_count
            contest["submission_count"] = submission_count
            contest["approved_submission_count"] = approved_count
            contest["fill_percentage"] = (participant_count / contest["max_participants"]) * 100
            contest["time_remaining"] = self._calculate_time_remaining(contest["end_date"])
            contest["time_until_start"] = self._calculate_time_until_start(contest["start_date"])
            contest["is_joined"] = is_joined
            contest["is_owner"] = is_owner
            contest["is_ended"] = is_ended
            contest["is_completed"] = is_completed
            contest["can_join"] = can_join
            contest["can_edit"] = can_edit
            contest["can_delete"] = can_delete
            contest["can_publish"] = can_publish
            contest["can_cancel"] = can_cancel
            contest["can_complete"] = can_complete
            
            # Note: We no longer auto-update status based on dates
            # Status transitions are explicit through publish/start/complete actions
            # or through the scheduler for auto-start/auto-complete
            
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
            
            # Calculate permissions based on state and participants
            can_edit = is_owner and contest["status"] == ContestStatus.DRAFT and participant_count == 0
            can_delete = is_owner and contest["status"] == ContestStatus.DRAFT and participant_count == 0
            can_publish = is_owner and contest["status"] == ContestStatus.DRAFT and task_count > 0
            can_cancel = is_owner and contest["status"] in [ContestStatus.DRAFT, ContestStatus.UPCOMING] and participant_count == 0
            
            # Can complete only if has participants, submissions, and approved submissions
            approved_count = await self.submissions.count_documents({
                "contest_id": contest_id,
                "status": "approved"
            })
            can_complete = (
                is_owner and 
                contest["status"] in [ContestStatus.ACTIVE, ContestStatus.JUDGING] and
                participant_count > 0 and
                submission_count > 0 and
                approved_count > 0
            )
            
            # Can join: not owner, not joined, status is UPCOMING/ACTIVE, not full, end_date not passed
            now = datetime.utcnow()
            end_date = contest.get("end_date")
            is_ended = end_date and end_date < now
            is_full = participant_count >= contest["max_participants"]
            is_completed = (
                contest["status"] == ContestStatus.COMPLETED or
                contest.get("prizes_distributed", False) or
                contest.get("refund_processed", False)
            )
            can_join = (
                not is_owner and
                not is_joined and
                contest["status"] in [ContestStatus.UPCOMING, ContestStatus.ACTIVE] and
                contest.get("is_active", False) and
                not is_full and
                not is_ended and
                not is_completed
            )
            
            # Add calculated fields
            contest["task_count"] = task_count
            contest["current_participants"] = participant_count
            contest["submission_count"] = submission_count
            contest["approved_submission_count"] = approved_count
            contest["fill_percentage"] = (participant_count / contest["max_participants"]) * 100
            contest["time_remaining"] = self._calculate_time_remaining(contest["end_date"])
            contest["time_until_start"] = self._calculate_time_until_start(contest["start_date"])
            contest["is_joined"] = is_joined
            contest["is_owner"] = is_owner
            contest["is_ended"] = is_ended
            contest["is_completed"] = is_completed
            contest["can_join"] = can_join
            contest["can_edit"] = can_edit
            contest["can_delete"] = can_delete
            contest["can_publish"] = can_publish
            contest["can_cancel"] = can_cancel
            contest["can_complete"] = can_complete
            
            # Note: We no longer auto-update status based on dates
            # Status transitions are explicit through publish/start/complete actions
            
            return contest
            
        except Exception as e:
            print(f"Error getting contest by slug: {str(e)}")
            return None
    
    async def get_contests(
        self,
        status: Optional[str] = None,
        category_id: Optional[str] = None,
        subcategory_id: Optional[str] = None,
        tag: Optional[str] = None,
        category: Optional[str] = None,  # Legacy support
        difficulty: Optional[str] = None,
        owner_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        user_id: Optional[str] = None,
        visibility: str = "public"  # public, owner, joined, all
    ) -> Tuple[List[Dict], int]:
        """
        Get contests with filtering, includes owner username.
        
        Filter parameters:
        - category_id: Filter by main category ID
        - subcategory_id: Filter by subcategory ID
        - tag: Filter by tag slug
        - category: Legacy filter by category name
        
        Visibility modes:
        - public: Only UPCOMING/ACTIVE/JUDGING with is_active=True (default for anonymous)
        - owner: All contests owned by owner_id (for owner dashboard)
        - joined: Contests user has joined
        - all: No visibility filter (admin only)
        """
        try:
            match_query = {}
            now = datetime.utcnow()
            
            # Apply visibility filter
            if visibility == "public":
                # Public can see:
                # - Active contests (upcoming, active, judging) with is_active=True
                # - Completed contests (regardless of is_active, for browsing history)
                # - Cancelled contests are NOT shown publicly
                match_query["$or"] = [
                    # Active contests must have is_active=True
                    {
                        "is_active": True,
                        "status": {"$in": [
                            ContestStatus.UPCOMING.value if hasattr(ContestStatus.UPCOMING, 'value') else ContestStatus.UPCOMING,
                            ContestStatus.ACTIVE.value if hasattr(ContestStatus.ACTIVE, 'value') else ContestStatus.ACTIVE,
                            ContestStatus.JUDGING.value if hasattr(ContestStatus.JUDGING, 'value') else ContestStatus.JUDGING
                        ]}
                    },
                    # Completed contests are always visible (for contest history)
                    {
                        "status": ContestStatus.COMPLETED.value if hasattr(ContestStatus.COMPLETED, 'value') else ContestStatus.COMPLETED
                    }
                ]
            elif visibility == "owner" and owner_id:
                # Owner sees all their contests
                match_query["owner_id"] = owner_id
            # For "joined" and "all", no visibility filter applied here
            
            if status:
                # Convert enum to string value if needed
                status_val = status.value if hasattr(status, 'value') else status
                
                if visibility == "public" and "$or" in match_query:
                    # For public visibility with status filter, replace the $or with a simpler query
                    # User is explicitly asking for a specific status
                    del match_query["$or"]
                    match_query["status"] = status_val
                    # For non-completed status, require is_active=True
                    if status_val != (ContestStatus.COMPLETED.value if hasattr(ContestStatus.COMPLETED, 'value') else ContestStatus.COMPLETED):
                        match_query["is_active"] = True
                elif "$and" in match_query:
                    match_query["$and"].append({"status": status_val})
                else:
                    match_query["status"] = status_val
            
            # Category/subcategory/tag filters
            if category_id:
                match_query["category_id"] = category_id
            if subcategory_id:
                match_query["subcategory_id"] = subcategory_id
            if tag:
                match_query["tags"] = tag  # MongoDB will match if tag is in array
            # Legacy category name filter
            if category and not category_id:
                match_query["category"] = category
            if difficulty:
                # Convert enum to string value if needed
                match_query["difficulty"] = difficulty.value if hasattr(difficulty, 'value') else difficulty
            if owner_id and visibility != "owner":
                # If specific owner_id requested and not already in owner mode
                match_query["owner_id"] = owner_id
            elif visibility == "public":
                # Filter out old contests without owner_id
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
                
                # Check if ended and can join
                now = datetime.utcnow()
                end_date = contest.get("end_date")
                is_ended = end_date and end_date < now
                is_full = participant_count >= contest.get("max_participants", 100)
                is_completed = (
                    contest["status"] == ContestStatus.COMPLETED or
                    contest.get("prizes_distributed", False) or
                    contest.get("refund_processed", False)
                )
                can_join = (
                    not is_owner and
                    not is_joined and
                    contest["status"] in [ContestStatus.UPCOMING, ContestStatus.ACTIVE] and
                    contest.get("is_active", False) and
                    not is_full and
                    not is_ended and
                    not is_completed
                )
                
                contest["is_joined"] = is_joined
                contest["is_owner"] = is_owner
                contest["is_ended"] = is_ended
                contest["is_completed"] = is_completed
                contest["can_join"] = can_join
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
        """
        Start a contest manually.
        
        Handles two cases:
        1. DRAFT -> ACTIVE (direct start, bypasses UPCOMING)
        2. UPCOMING -> ACTIVE (early start before scheduled time)
        
        For proper lifecycle, use publish_contest first to go DRAFT -> UPCOMING,
        then let auto_start handle UPCOMING -> ACTIVE.
        """
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can start"
            
            current_status = contest["status"]
            
            # Check status - allow from DRAFT or UPCOMING
            if current_status not in [ContestStatus.DRAFT, ContestStatus.UPCOMING]:
                if current_status == ContestStatus.ACTIVE:
                    return False, "Contest is already active"
                return False, f"Cannot start contest in {current_status} status"
            
            # Check if has tasks
            task_count = await self.tasks.count_documents({"contest_id": contest_id})
            if task_count == 0:
                return False, "Cannot start contest without tasks"
            
            now = datetime.utcnow()
            
            # Build update data
            update_data = {
                "status": ContestStatus.ACTIVE,
                "is_active": True,  # Make visible
                "updated_at": now
            }
            
            # If starting from DRAFT, also set published_at
            if current_status == ContestStatus.DRAFT:
                update_data["published_at"] = now
            
            # If start_date is in the future, update it to now
            if contest["start_date"] > now:
                update_data["start_date"] = now
            
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": update_data}
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
                    "action": "manual_start",
                    "previous_status": current_status,
                    "participant_count": participant_count,
                    "task_count": task_count,
                    "prize_amount": contest.get("total_prize", 0),
                    "started_at": now.isoformat()
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
        """
        User joins a contest.
        If contest has an entry fee, deducts from user's wallet.
        """
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Cannot join own contest
            if str(contest["owner_id"]) == user_id:
                return False, "Cannot join your own contest"
            
            # Check status - can join UPCOMING or ACTIVE contests
            if contest["status"] not in [ContestStatus.UPCOMING, ContestStatus.ACTIVE]:
                if contest["status"] == ContestStatus.DRAFT:
                    return False, "Contest is not published yet"
                return False, "Contest registration closed"
            
            # Check if contest is active (visible to public)
            if not contest.get("is_active", False):
                return False, "Contest is not available for registration"
            
            # CRITICAL: Check if contest end_date has passed
            now = datetime.utcnow()
            end_date = contest.get("end_date")
            if end_date and end_date < now:
                return False, "Contest has ended. Registration is closed."
            
            # CRITICAL: Check if prizes already distributed or refund processed
            if contest.get("prizes_distributed", False):
                return False, "Contest has been completed. Prizes already distributed."
            if contest.get("refund_processed", False):
                return False, "Contest has been completed. Refund already processed."
            
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
            
            # Check and deduct entry fee if applicable
            entry_fee = contest.get("entry_fee", 0.0)
            transaction = None
            
            if entry_fee > 0:
                wallet_utils = WalletUtils(self.db)
                
                # Check balance first
                available_balance, _ = await wallet_utils.get_balance(user_id)
                if available_balance < entry_fee:
                    return False, f"Insufficient balance. Entry fee: {entry_fee} credits. Your balance: {available_balance} credits"
                
                # Deduct entry fee
                success, message, transaction = await wallet_utils.deduct_balance(
                    user_id=user_id,
                    amount=entry_fee,
                    category=TransactionCategory.CONTEST_ENTRY,
                    description=f"Entry fee for contest: {contest.get('title', 'Unknown')}",
                    reference_type="contest",
                    reference_id=contest_id,
                    idempotency_key=f"ENTRY_{contest_id}_{user_id}"
                )
                
                if not success:
                    return False, f"Failed to deduct entry fee: {message}"
            
            # Add participant
            participant = {
                "contest_id": contest_id,
                "user_id": user_id,
                "username": username,
                "joined_at": datetime.utcnow(),
                # Simple scoring
                "total_score": 0,
                "approved_tasks": 0,
                "pending_tasks": 0,
                # Weighted scoring (for prize distribution)
                "weighted_score": 0.0,
                "task_scores": [],  # [{task_id, score, weightage, weighted_score}]
                # Earnings
                "earnings": 0.0,
                "prize_distributed": False,
                "prize_distributed_at": None,
                # Entry fee tracking
                "entry_fee_paid": entry_fee,
                "entry_fee_transaction_id": transaction["transaction_id"] if transaction else None
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
                    "fill_percentage": ((participant_count + 1) / contest["max_participants"]) * 100,
                    "entry_fee_paid": entry_fee,
                    "transaction_id": transaction["transaction_id"] if transaction else None
                }
            )
            
            return True, "Successfully joined contest"
            
        except Exception as e:
            print(f"Error joining contest: {str(e)}")
            return False, f"Failed to join: {str(e)}"
    
    async def leave_contest(self, contest_id: str, user_id: str) -> Tuple[bool, str]:
        """Leave a contest (only if contest hasn't started - UPCOMING status)"""
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Can only leave if contest is UPCOMING (before it starts)
            if contest["status"] not in [ContestStatus.UPCOMING]:
                if contest["status"] == ContestStatus.ACTIVE:
                    return False, "Cannot leave after contest has started"
                return False, "Cannot leave contest in current status"
            
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
    
    # ==========================================
    # STATE TRANSITION VALIDATION HELPERS
    # ==========================================
    
    async def can_publish(self, contest: dict) -> Tuple[bool, str]:
        """
        Check if contest can be published (DRAFT -> UPCOMING).
        
        Requirements:
        - Status must be DRAFT
        - Must have at least 1 task
        - start_date must be in the future
        """
        if contest["status"] != ContestStatus.DRAFT:
            return False, "Contest must be in draft status to publish"
        
        contest_id = str(contest["_id"])
        task_count = await self.tasks.count_documents({"contest_id": contest_id})
        
        if task_count == 0:
            return False, "Cannot publish contest without tasks"
        
        now = datetime.utcnow()
        if contest["start_date"] <= now:
            return False, "Start date must be in the future to publish"
        
        return True, "Contest can be published"
    
    async def can_cancel(self, contest: dict) -> Tuple[bool, str]:
        """
        Check if contest can be cancelled.
        
        Requirements:
        - Status must be DRAFT or UPCOMING
        - No participants joined
        """
        if contest["status"] not in [ContestStatus.DRAFT, ContestStatus.UPCOMING]:
            return False, "Only draft or upcoming contests can be cancelled"
        
        contest_id = str(contest["_id"])
        participant_count = await self.participants.count_documents({"contest_id": contest_id})
        
        if participant_count > 0:
            return False, "Cannot cancel contest with participants. This protects users who have joined."
        
        return True, "Contest can be cancelled"
    
    async def can_complete(self, contest: dict) -> Tuple[bool, str, dict]:
        """
        Check if contest can be completed.
        
        Requirements:
        - Status must be ACTIVE or JUDGING
        - Has at least 1 participant
        - Has at least 1 submission
        - Has at least 1 approved submission
        
        Returns: (can_complete, reason, stats)
        """
        if contest["status"] not in [ContestStatus.ACTIVE, ContestStatus.JUDGING]:
            return False, "Contest must be active or in judging status", {}
        
        contest_id = str(contest["_id"])
        
        # Check participants
        participant_count = await self.participants.count_documents({"contest_id": contest_id})
        if participant_count == 0:
            return False, "Cannot complete contest without participants", {"participants": 0}
        
        # Check submissions
        submission_count = await self.submissions.count_documents({"contest_id": contest_id})
        if submission_count == 0:
            return False, "Cannot complete contest without submissions", {
                "participants": participant_count,
                "submissions": 0
            }
        
        # Check approved submissions
        approved_count = await self.submissions.count_documents({
            "contest_id": contest_id,
            "status": "approved"
        })
        
        if approved_count == 0:
            return False, "Cannot complete contest without at least one approved submission. Please review pending submissions.", {
                "participants": participant_count,
                "submissions": submission_count,
                "approved": 0
            }
        
        return True, "Contest can be completed", {
            "participants": participant_count,
            "submissions": submission_count,
            "approved": approved_count
        }
    
    async def can_start_now(self, contest: dict) -> Tuple[bool, str]:
        """
        Check if contest can be started immediately (for manual start).
        
        Requirements:
        - Status must be UPCOMING
        - is_active must be True
        """
        if contest["status"] != ContestStatus.UPCOMING:
            return False, "Only upcoming contests can be started"
        
        if not contest.get("is_active", False):
            return False, "Contest is not active. Please publish first."
        
        return True, "Contest can be started"
    
    # ==========================================
    # STATE TRANSITION METHODS
    # ==========================================
    
    async def publish_contest(self, contest_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Publish a contest (DRAFT -> UPCOMING).
        
        This makes the contest visible to the public.
        Users can now join (before start_date).
        
        Auto-start will occur at start_date.
        
        IMPORTANT: This also locks the prize pool from the owner's wallet.
        """
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can publish"
            
            # Validate can publish
            can_pub, reason = await self.can_publish(contest)
            if not can_pub:
                return False, reason
            
            now = datetime.utcnow()
            prize_pool = contest.get("total_prize", 0)
            
            # Lock the prize pool from owner's wallet
            from app.services.contest.contest_fee import ContestFeeService
            fee_service = ContestFeeService(self.db)
            
            payment_success, payment_message, payment_details = await fee_service.process_contest_creation_payment(
                user_id=user_id,
                contest_id=contest_id,
                contest_title=contest.get("title", "Unknown"),
                prize_pool=prize_pool
            )
            
            if not payment_success:
                return False, f"Failed to lock prize pool: {payment_message}"
            
            # Update contest
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": {
                    "status": ContestStatus.UPCOMING,
                    "is_active": True,
                    "published_at": now,
                    "prize_pool_locked": True,
                    "updated_at": now
                }}
            )
            
            # Log to audit trail
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.CONTEST_STARTED,  # Using STARTED for publish too
                user_id=user_id,
                username=contest.get("owner_name", "Unknown"),
                entity_type="contest",
                entity_id=contest_id,
                metadata={
                    "action": "published",
                    "previous_status": ContestStatus.DRAFT,
                    "new_status": ContestStatus.UPCOMING,
                    "start_date": contest["start_date"].isoformat(),
                    "published_at": now.isoformat(),
                    "prize_pool_locked": prize_pool,
                    "payment_details": payment_details
                }
            )
            
            return True, "Contest published successfully. Prize pool locked. It will auto-start at the scheduled time."
            
        except Exception as e:
            return False, f"Failed to publish: {str(e)}"
    
    async def cancel_contest(self, contest_id: str, user_id: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Cancel a contest (DRAFT/UPCOMING -> CANCELLED).
        
        Refunds the locked prize pool to owner (minus cancellation fee if configured).
        Only allowed if no participants have joined.
        """
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found", None
            
            # Check ownership
            if str(contest["owner_id"]) != user_id:
                return False, "Only contest owner can cancel", None
            
            # Validate can cancel
            can_can, reason = await self.can_cancel(contest)
            if not can_can:
                return False, reason, None
            
            now = datetime.utcnow()
            refund_details = None
            
            # Process refund if prize pool was locked
            if contest.get("prize_pool_locked", False):
                from app.services.contest.contest_fee import ContestFeeService
                fee_service = ContestFeeService(self.db)
                
                refund_success, refund_message, refund_details = await fee_service.process_contest_cancellation_refund(
                    user_id=user_id,
                    contest_id=contest_id,
                    contest_title=contest.get("title", "Unknown"),
                    prize_pool=contest.get("total_prize", 0)
                )
                
                if not refund_success:
                    return False, f"Failed to process refund: {refund_message}", None
            
            # Update contest
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": {
                    "status": ContestStatus.CANCELLED,
                    "is_active": False,
                    "cancelled_at": now,
                    "prize_pool_locked": False,
                    "updated_at": now
                }}
            )
            
            # Log to audit trail
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.CONTEST_UPDATED,
                user_id=user_id,
                username=contest.get("owner_name", "Unknown"),
                entity_type="contest",
                entity_id=contest_id,
                changes={
                    "status": {"from": contest["status"], "to": ContestStatus.CANCELLED}
                },
                metadata={
                    "action": "cancelled",
                    "refund_processed": refund_details is not None,
                    "refund_details": refund_details
                }
            )
            
            return True, "Contest cancelled successfully. Refund processed.", refund_details
            
        except Exception as e:
            return False, f"Failed to cancel: {str(e)}", None
    
    async def auto_start_contest(self, contest_id: str) -> Tuple[bool, str]:
        """
        Auto-start a contest (UPCOMING -> ACTIVE).
        
        Called by scheduler when start_date is reached.
        This is a system action, not user-triggered.
        """
        try:
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            
            if not contest:
                return False, "Contest not found"
            
            # Validate state
            if contest["status"] != ContestStatus.UPCOMING:
                return False, "Contest is not in upcoming status"
            
            if not contest.get("is_active", False):
                return False, "Contest is not active"
            
            now = datetime.utcnow()
            
            # Update contest
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": {
                    "status": ContestStatus.ACTIVE,
                    "updated_at": now
                }}
            )
            
            # Log to audit trail
            participant_count = await self.participants.count_documents({"contest_id": contest_id})
            task_count = await self.tasks.count_documents({"contest_id": contest_id})
            
            await self.audit_service.log_action(
                contest_id=contest_id,
                action=AuditAction.CONTEST_STARTED,
                user_id="system",
                username="System",
                entity_type="contest",
                entity_id=contest_id,
                metadata={
                    "action": "auto_started",
                    "trigger": "scheduled",
                    "participant_count": participant_count,
                    "task_count": task_count,
                    "started_at": now.isoformat()
                }
            )
            
            print(f"[SCHEDULER] Contest {contest_id} auto-started with {participant_count} participants")
            return True, "Contest auto-started successfully"
            
        except Exception as e:
            print(f"[ERROR] Failed to auto-start contest {contest_id}: {str(e)}")
            return False, f"Failed to auto-start: {str(e)}"
    
    async def get_participant_count(self, contest_id: str) -> int:
        """Get number of participants in a contest"""
        return await self.participants.count_documents({"contest_id": contest_id})
    
    async def get_submission_count(self, contest_id: str) -> int:
        """Get number of submissions in a contest"""
        return await self.submissions.count_documents({"contest_id": contest_id})
    
    async def get_approved_submission_count(self, contest_id: str) -> int:
        """Get number of approved submissions in a contest"""
        return await self.submissions.count_documents({
            "contest_id": contest_id,
            "status": "approved"
        })