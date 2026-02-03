from fastapi import APIRouter, Depends, File, UploadFile, Form, Query
from typing import Optional
from datetime import datetime
from bson import ObjectId
from app.database import Database
from app.services.contest.contest import ContestService
from app.services.contest.contest_widgets import ContestWidgetsService
from app.routes.auth.dependencies import get_current_user
from app.models.contest.contest import (
    ContestCreate,
    ContestUpdate,
    ContestStatus,
    ContestDifficulty,
    ContestType
)
from app.utils.response import success_response, error_response, validation_error_response
from app.utils.file_upload import FileUploadService

router = APIRouter(prefix="/contests", tags=["Contests"])


def convert_contest_to_json(contest: dict) -> dict:
    """Convert contest document to JSON"""
    contest["id"] = str(contest["_id"])
    del contest["_id"]
    
    # Convert dates
    for field in ["start_date", "end_date", "created_at", "updated_at"]:
        if contest.get(field):
            contest[field] = contest[field].isoformat()
    
    # Remove voter arrays
    contest.pop("upvoters", None)
    contest.pop("downvoters", None)
    
    return contest


async def resolve_contest_id(identifier: str, db) -> Optional[str]:
    """
    Resolve contest identifier to actual contest_id.
    Accepts both ObjectId and slug.
    """
    is_object_id = len(identifier) == 24 and all(c in '0123456789abcdef' for c in identifier.lower())
    
    if is_object_id:
        return identifier
    else:
        # Look up by slug
        contest_service = ContestService(db)
        contest = await contest_service.get_contest_by_slug(identifier)
        if contest:
            return str(contest["_id"])
        return None


@router.post("/create")
async def create_contest(
    title: str = Form(..., min_length=10, max_length=200),
    description: str = Form(..., min_length=50),
    category: str = Form(...),
    difficulty: ContestDifficulty = Form(...),
    contest_type: ContestType = Form(ContestType.INDIVIDUAL),
    total_prize: float = Form(..., gt=0),
    max_participants: int = Form(..., gt=0),
    start_date: str = Form(...),
    end_date: str = Form(...),
    rules: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new contest (any authenticated user can create).
    
    - Contest starts in DRAFT status
    - Owner can add tasks before starting
    - Must have at least 1 task to start
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # Parse dates
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except:
        return validation_error_response(
            errors={"dates": "Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}
        )
    
    # Validate dates
    if end_dt <= start_dt:
        return validation_error_response(
            errors={"end_date": "End date must be after start date"}
        )
    
    # Handle cover image
    cover_image_url = None
    if cover_image and cover_image.filename:
        try:
            file_service = FileUploadService()
            user_id = str(current_user["_id"])
            file_info = await file_service.save_file(cover_image, user_id)
            cover_image_url = file_info["file_url"]
        except ValueError as e:
            return validation_error_response(errors={"cover_image": str(e)})
    
    # Create contest
    db = Database.get_db()
    contest_service = ContestService(db)
    
    contest_data = ContestCreate(
        title=title,
        description=description,
        category=category,
        difficulty=difficulty,
        contest_type=contest_type,
        total_prize=total_prize,
        max_participants=max_participants,
        start_date=start_dt,
        end_date=end_dt,
        rules=rules
    )
    
    contest = await contest_service.create_contest(
        contest_data=contest_data,
        owner_id=str(current_user["_id"]),
        owner_name=current_user.get("full_name") or current_user.get("email"),
        cover_image=cover_image_url
    )
    
    if not contest:
        return error_response(message="Failed to create contest")
    
    return success_response(
        message="Contest created successfully",
        data={"contest": convert_contest_to_json(contest)},
        status_code=201
    )


@router.get("")
async def get_contests(
    status: Optional[ContestStatus] = Query(None),
    category: Optional[str] = Query(None),
    difficulty: Optional[ContestDifficulty] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get all contests with filtering.
    
    - Anyone can view (public)
    - Filter by status, category, difficulty
    - Shows if user joined each contest
    """
    db = Database.get_db()
    contest_service = ContestService(db)
    
    user_id = str(current_user["_id"]) if current_user else None
    
    contests, total = await contest_service.get_contests(
        status=status,
        category=category,
        difficulty=difficulty,
        page=page,
        limit=limit,
        user_id=user_id
    )
    
    # Convert to JSON
    contests_data = [convert_contest_to_json(c) for c in contests]
    
    # Count by status (use .value to get string values, filter out old contests without owner_id)
    active_count = await db.contests.count_documents({
        "status": ContestStatus.ACTIVE.value,
        "owner_id": {"$exists": True}
    })
    draft_count = await db.contests.count_documents({
        "status": ContestStatus.DRAFT.value,
        "owner_id": {"$exists": True}
    })
    judging_count = await db.contests.count_documents({
        "status": ContestStatus.JUDGING.value,
        "owner_id": {"$exists": True}
    })
    completed_count = await db.contests.count_documents({
        "status": ContestStatus.COMPLETED.value,
        "owner_id": {"$exists": True}
    })
    
    return success_response(
        message="Contests retrieved successfully",
        data={
            "contests": contests_data,
            "counts": {
                "draft": draft_count,
                "active": active_count,
                "judging": judging_count,
                "completed": completed_count
            },
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/my-contests")
async def get_my_contests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get contests created by current user"""
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    contest_service = ContestService(db)
    
    contests, total = await contest_service.get_contests(
        owner_id=str(current_user["_id"]),
        page=page,
        limit=limit,
        user_id=str(current_user["_id"])
    )
    
    contests_data = [convert_contest_to_json(c) for c in contests]
    
    return success_response(
        message="Your contests retrieved successfully",
        data={
            "contests": contests_data,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/joined")
async def get_joined_contests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query(None, pattern="^(active|completed|all)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get contests current user has joined/participated in.
    
    Authenticated endpoint - shows user's contest participation history.
    
    This is a convenience endpoint that automatically uses the logged-in
    user's ID instead of requiring it in the URL path.
    
    Use this for "My Participated Contests" on user's own profile.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    user_id = str(current_user["_id"])
    
    try:
        db = Database.get_db()
        
        # Build query for participated contests
        participant_query = {"user_id": user_id}
        
        # Get all contest_ids user participated in
        participants = await db.contest_participants.find(
            participant_query
        ).to_list(length=None)
        
        if not participants:
            return success_response(
                message="No participated contests found",
                data={
                    "contests": [],
                    "total": 0,
                    "pagination": {
                        "total": 0,
                        "page": page,
                        "limit": limit,
                        "total_pages": 0
                    }
                }
            )
        
        contest_ids = [ObjectId(p["contest_id"]) for p in participants]
        
        # Build contest query
        contest_query = {
            "_id": {"$in": contest_ids},
            "owner_id": {"$exists": True}
        }
        
        # Filter by status if provided
        if status and status != "all":
            contest_query["status"] = status
        
        # Get total count
        total = await db.contests.count_documents(contest_query)
        
        # Get paginated contests
        skip = (page - 1) * limit
        contests = await db.contests.find(contest_query).sort(
            "created_at", -1
        ).skip(skip).limit(limit).to_list(length=limit)
        
        # Enrich with participation data
        contests_data = []
        for contest in contests:
            contest_id = str(contest["_id"])
            
            # Find user's participation record
            participant = next(
                (p for p in participants if p["contest_id"] == contest_id),
                None
            )
            
            contest_json = convert_contest_to_json(contest)
            
            # Add participation info
            if participant:
                contest_json["participation"] = {
                    "joined_at": participant.get("joined_at").isoformat() if participant.get("joined_at") else None,
                    "total_score": participant.get("total_score", 0),
                    "approved_tasks": participant.get("approved_tasks", 0),
                    "pending_tasks": participant.get("pending_tasks", 0),
                    "rank": None
                }
                
                # Get user's rank in contest
                all_participants = await db.contest_participants.find({
                    "contest_id": contest_id
                }).sort("total_score", -1).to_list(length=None)
                
                for idx, p in enumerate(all_participants, 1):
                    if p["user_id"] == user_id:
                        contest_json["participation"]["rank"] = idx
                        break
            
            contests_data.append(contest_json)
        
        total_pages = (total + limit - 1) // limit
        
        return success_response(
            message="Joined contests retrieved successfully",
            data={
                "contests": contests_data,
                "total": total,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages
                }
            }
        )
        
    except Exception as e:
        print(f"Error getting joined contests: {str(e)}")
        return error_response(
            message=f"Failed to retrieve joined contests: {str(e)}",
            status_code=500
        )


@router.get("/{identifier}")
async def get_contest(
    identifier: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get contest details by ID or slug.
    
    - If identifier is a valid 24-character hex string, treats it as contest_id
    - Otherwise, treats it as a slug
    """
    db = Database.get_db()
    contest_service = ContestService(db)
    
    user_id = str(current_user["_id"]) if current_user else None
    
    # Check if identifier is a valid ObjectId (24 hex characters)
    is_object_id = len(identifier) == 24 and all(c in '0123456789abcdef' for c in identifier.lower())
    
    if is_object_id:
        contest = await contest_service.get_contest_by_id(identifier, user_id)
        contest_id = identifier
    else:
        contest = await contest_service.get_contest_by_slug(identifier, user_id)
        contest_id = str(contest["_id"]) if contest else None
    
    if not contest:
        return error_response(
            message="Contest not found",
            status_code=404
        )
    
    # Increment view count
    await contest_service.increment_view_count(contest_id)
    
    return success_response(
        message="Contest retrieved successfully",
        data={"contest": convert_contest_to_json(contest)}
    )


@router.put("/{contest_id}")
async def update_contest(
    contest_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    difficulty: Optional[ContestDifficulty] = Form(None),
    contest_type: Optional[ContestType] = Form(None),
    total_prize: Optional[float] = Form(None),
    max_participants: Optional[int] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    rules: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a contest (only owner, only in DRAFT status).
    
    - Cannot edit after contest has started
    - All fields optional
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # Parse dates if provided
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            return validation_error_response(
                errors={"start_date": "Invalid date format"}
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            return validation_error_response(
                errors={"end_date": "Invalid date format"}
            )
    
    # Validate dates
    if start_dt and end_dt and end_dt <= start_dt:
        return validation_error_response(
            errors={"end_date": "End date must be after start date"}
        )
    
    db = Database.get_db()
    contest_service = ContestService(db)
    
    update_data = ContestUpdate(
        title=title,
        description=description,
        category=category,
        difficulty=difficulty,
        contest_type=contest_type,
        total_prize=total_prize,
        max_participants=max_participants,
        start_date=start_dt,
        end_date=end_dt,
        rules=rules
    )
    
    success, message = await contest_service.update_contest(
        contest_id=contest_id,
        update_data=update_data,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"updated": True}
    )


@router.delete("/{contest_id}")
async def delete_contest(
    contest_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a contest (only owner, only in DRAFT status).
    
    - Cannot delete after contest has started
    - Cannot delete if has participants
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    contest_service = ContestService(db)
    
    success, message = await contest_service.delete_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"deleted": True}
    )


@router.post("/{contest_identifier}/start")
async def start_contest(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a contest (only owner, changes status from DRAFT to ACTIVE).
    
    - Requires at least 1 task
    - After starting, cannot edit tasks
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    contest_service = ContestService(db)
    
    success, message = await contest_service.start_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"started": True}
    )


@router.post("/{contest_identifier}/complete")
async def complete_contest(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Complete a contest (only owner, changes status to COMPLETED).
    
    - Marks contest as finished
    - Announces winners
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    contest_service = ContestService(db)
    
    success, message = await contest_service.complete_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"completed": True}
    )


@router.post("/{contest_identifier}/join")
async def join_contest(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Join a contest as a participant (accepts contest ID or slug).
    
    - Cannot join own contest
    - Cannot join if full
    - Cannot join if registration closed
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    contest_service = ContestService(db)
    
    success, message = await contest_service.join_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"]),
        username=current_user.get("username") or current_user.get("full_name") or current_user.get("email")
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"joined": True}
    )


@router.post("/{contest_identifier}/leave")
async def leave_contest(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Leave a contest (accepts contest ID or slug).
    
    - Only before contest starts
    - Cannot leave if has submissions
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    contest_service = ContestService(db)
    
    success, message = await contest_service.leave_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"left": True}
    )


@router.post("/{contest_identifier}/vote")
async def vote_on_contest(
    contest_identifier: str,
    vote_type: str = Form(..., pattern="^(upvote|downvote|remove)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Vote on a contest (accepts contest ID or slug).
    
    - upvote: Like the contest
    - downvote: Dislike the contest
    - remove: Remove vote
    - Cannot vote on own contest
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    contest_service = ContestService(db)
    
    success, message, net_votes = await contest_service.vote_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"]),
        vote_type=vote_type
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"vote_type": vote_type, "net_votes": net_votes}
    )


@router.get("/{contest_identifier}/participants")
async def get_contest_participants(
    contest_identifier: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """Get all participants of a contest (accepts contest ID or slug)"""
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    skip = (page - 1) * limit
    
    # Use aggregation with $lookup to get fresh username from users collection
    pipeline = [
        {"$match": {"contest_id": contest_id}},
        {"$sort": {"joined_at": 1}},
        {"$skip": skip},
        {"$limit": limit},
        # Lookup user to get current username
        {
            "$lookup": {
                "from": "users",
                "let": {"user_id": {"$toObjectId": "$user_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$user_id"]}}},
                    {"$project": {"username": 1, "full_name": 1, "email": 1, "profile_picture": 1}}
                ],
                "as": "user_info"
            }
        },
        {"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}},
        # Add user fields from lookup
        {
            "$addFields": {
                "username": {
                    "$ifNull": [
                        "$user_info.username",
                        {"$ifNull": ["$user_info.full_name", "$user_name"]}  # Fallback to old user_name
                    ]
                },
                "full_name": "$user_info.full_name",
                "profile_picture": "$user_info.profile_picture"
            }
        },
        # Remove internal fields
        {"$project": {"user_info": 0, "user_name": 0}}
    ]
    
    participants = await db.contest_participants.aggregate(pipeline).to_list(length=limit)
    total = await db.contest_participants.count_documents({"contest_id": contest_id})
    
    # Convert to JSON
    participants_data = []
    for p in participants:
        p["id"] = str(p["_id"])
        del p["_id"]
        if p.get("joined_at"):
            p["joined_at"] = p["joined_at"].isoformat()
        # Ensure user fields are always present
        if "full_name" not in p:
            p["full_name"] = None
        if "profile_picture" not in p:
            p["profile_picture"] = None
        participants_data.append(p)
    
    return success_response(
        message="Participants retrieved successfully",
        data={
            "participants": participants_data,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/{contest_identifier}/leaderboard")
async def get_contest_leaderboard(
    contest_identifier: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get contest leaderboard sorted by total score (accepts contest ID or slug).
    
    - Shows participants ranked by approved task points
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    skip = (page - 1) * limit
    
    # Use aggregation with $lookup to get fresh username from users collection
    pipeline = [
        {"$match": {"contest_id": contest_id}},
        {"$sort": {"total_score": -1}},
        {"$skip": skip},
        {"$limit": limit},
        # Lookup user to get current username
        {
            "$lookup": {
                "from": "users",
                "let": {"user_id": {"$toObjectId": "$user_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$user_id"]}}},
                    {"$project": {"username": 1, "full_name": 1, "profile_picture": 1}}
                ],
                "as": "user_info"
            }
        },
        {"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}},
        # Add user fields from lookup
        {
            "$addFields": {
                "username": {
                    "$ifNull": [
                        "$user_info.username",
                        {"$ifNull": ["$user_info.full_name", "$user_name"]}
                    ]
                },
                "full_name": "$user_info.full_name",
                "profile_picture": "$user_info.profile_picture"
            }
        }
    ]
    
    participants = await db.contest_participants.aggregate(pipeline).to_list(length=limit)
    total = await db.contest_participants.count_documents({"contest_id": contest_id})
    
    # Build leaderboard
    leaderboard = []
    for idx, p in enumerate(participants, start=(page - 1) * limit + 1):
        leaderboard.append({
            "rank": idx,
            "user_id": p["user_id"],
            "username": p.get("username"),
            "full_name": p.get("full_name"),
            "profile_picture": p.get("profile_picture"),
            "total_score": p.get("total_score", 0),
            "approved_tasks": p.get("approved_tasks", 0),
            "pending_tasks": p.get("pending_tasks", 0)
        })
    
    return success_response(
        message="Leaderboard retrieved successfully",
        data={
            "leaderboard": leaderboard,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


# ============================================================================
# CONTEST SIDEBAR WIDGETS - For Contest Details Page
# ============================================================================

@router.get("/{contest_identifier}/widgets/my-progress")
async def get_my_contest_progress(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user's progress in this contest (accepts contest ID or slug).
    
    Returns:
    - Rank in contest
    - Total score
    - Tasks completed/pending/revision
    - Completion percentage
    
    Widget: "Your Progress"
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    widgets_service = ContestWidgetsService(db)
    
    progress = await widgets_service.get_user_progress(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    if not progress:
        return error_response(
            message="You haven't joined this contest yet",
            status_code=404
        )
    
    return success_response(
        message="Progress retrieved successfully",
        data={"progress": progress}
    )


@router.get("/{contest_identifier}/widgets/stats")
async def get_contest_stats_widget(contest_identifier: str):
    """
    Get enhanced contest statistics for sidebar widget (accepts contest ID or slug).
    
    Returns:
    - Total participants
    - Total submissions
    - Approval rate
    - Most popular task
    - Average score
    - Active participants (24h)
    - Time remaining
    
    Widget: "Contest Stats"
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    widgets_service = ContestWidgetsService(db)
    
    stats = await widgets_service.get_contest_stats(contest_id)
    
    return success_response(
        message="Contest stats retrieved successfully",
        data={"stats": stats}
    )


@router.get("/{contest_identifier}/widgets/owner-info")
async def get_contest_owner_widget(contest_identifier: str):
    """
    Get contest owner information and their other contests (accepts contest ID or slug).
    
    Returns:
    - Owner profile
    - Total contests created
    - Average rating
    - Other active contests (max 5)
    
    Widget: "Organized By"
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    # Get contest to find owner
    contest = await db.contests.find_one({"_id": ObjectId(contest_id)})
    
    if not contest:
        return error_response(
            message="Contest not found",
            status_code=404
        )
    
    owner_id = contest.get("owner_id")
    if not owner_id:
        return error_response(
            message="Contest has no owner",
            status_code=404
        )
    
    widgets_service = ContestWidgetsService(db)
    owner_info = await widgets_service.get_contest_owner_info(
        owner_id=owner_id,
        exclude_contest_id=contest_id
    )
    
    if not owner_info:
        return error_response(
            message="Owner information not found",
            status_code=404
        )
    
    return success_response(
        message="Owner info retrieved successfully",
        data={"owner": owner_info}
    )


@router.get("/{contest_identifier}/widgets/similar-contests")
async def get_similar_contests_widget(
    contest_identifier: str,
    limit: int = Query(5, ge=1, le=10)
):
    """
    Get similar/related contests for sidebar (accepts contest ID or slug).
    
    Returns contests that are:
    - Same category or difficulty
    - Currently active or upcoming
    - Not the current contest
    
    Widget: "Similar Contests"
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    widgets_service = ContestWidgetsService(db)
    
    similar = await widgets_service.get_similar_contests(
        contest_id=contest_id,
        limit=limit
    )
    
    return success_response(
        message="Similar contests retrieved successfully",
        data={
            "contests": similar,
            "total": len(similar)
        }
    )


@router.get("/{contest_identifier}/widgets/recent-activity")
async def get_contest_activity_widget(
    contest_identifier: str,
    limit: int = Query(10, ge=5, le=20)
):
    """
    Get recent activity feed for the contest (accepts contest ID or slug).
    
    Includes:
    - New submissions
    - Approved submissions
    - New participants
    - Recent completions
    
    Widget: "Recent Activity"
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    widgets_service = ContestWidgetsService(db)
    
    activities = await widgets_service.get_recent_activity(
        contest_id=contest_id,
        limit=limit
    )
    
    return success_response(
        message="Recent activity retrieved successfully",
        data={
            "activities": activities,
            "total": len(activities)
        }
    )


@router.get("/{contest_identifier}/widgets/top-performers")
async def get_top_performers_widget(
    contest_identifier: str,
    time_period: str = Query("week", pattern="^(day|week|month|all_time)$"),
    limit: int = Query(5, ge=3, le=10)
):
    """
    Get top performers in the contest for a time period (accepts contest ID or slug).
    
    time_period: "day", "week", "month", "all_time"
    
    Returns:
    - User name
    - Approved tasks count
    - Total points earned
    - Submissions count
    
    Widget: "Top Performers This Week/Day"
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    widgets_service = ContestWidgetsService(db)
    
    performers = await widgets_service.get_top_performers(
        contest_id=contest_id,
        time_period=time_period,
        limit=limit
    )
    
    return success_response(
        message=f"Top performers ({time_period}) retrieved successfully",
        data={
            "performers": performers,
            "time_period": time_period,
            "total": len(performers)
        }
    )


@router.get("/{contest_identifier}/widgets/task-stats")
async def get_task_completion_widget(contest_identifier: str):
    """
    Get task completion statistics for progress bars (accepts contest ID or slug).
    
    Returns for each task:
    - Task title
    - Total submissions
    - Unique submitters
    - Completion percentage
    - Approval rate
    
    Widget: "Task Completion Stats"
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    widgets_service = ContestWidgetsService(db)
    
    task_stats = await widgets_service.get_task_completion_stats(contest_id)
    
    return success_response(
        message="Task completion stats retrieved successfully",
        data={
            "tasks": task_stats,
            "total_tasks": len(task_stats)
        }
    )
