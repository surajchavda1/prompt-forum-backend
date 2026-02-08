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
    """Convert contest document to JSON-serializable format"""
    from datetime import datetime as dt, timedelta
    from bson import ObjectId
    
    def serialize_value(value):
        """Recursively serialize non-JSON-serializable values"""
        if isinstance(value, dt):
            return value.isoformat()
        elif isinstance(value, timedelta):
            return str(value)
        elif isinstance(value, ObjectId):
            return str(value)
        elif isinstance(value, dict):
            return {k: serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [serialize_value(item) for item in value]
        return value
    
    # Convert _id to id string
    contest["id"] = str(contest["_id"])
    del contest["_id"]
    
    # Serialize all values recursively (handles datetime, timedelta, ObjectId, nested dicts)
    for key, value in list(contest.items()):
        contest[key] = serialize_value(value)
    
    # Remove voter arrays (security - don't expose who voted)
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
    category_id: str = Form(..., description="Main category ID"),
    subcategory_id: Optional[str] = Form(None, description="Subcategory ID"),
    tags: str = Form("", description="Comma-separated tag slugs"),
    difficulty: ContestDifficulty = Form(...),
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
    
    NOTE: Contest type is always INDIVIDUAL (team contests not supported yet).
    
    CATEGORY/TAGS:
    - category_id: Main category ID (required)
    - subcategory_id: Subcategory ID (optional but recommended)
    - tags: Comma-separated tag slugs (must be valid for selected subcategory)
    
    CREDIT REQUIREMENTS:
    - User must have enough credits: prize_pool + platform_fee
    - Platform fee is calculated dynamically from database config
    - Prize pool credits are locked (held until contest ends)
    - Platform fee is deducted immediately
    
    - Contest starts in DRAFT status
    - Owner can add tasks before starting
    - Must have at least 1 task to start
    """
    from app.services.contest.contest_fee import ContestFeeService
    from app.services.forum.category import CategoryService
    from app.services.forum.tag import TagService
    
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
    
    db = Database.get_db()
    category_service = CategoryService(db)
    tag_service = TagService(db)
    
    # Validate category exists and is a parent category (not a subcategory)
    category = await category_service.get_category_by_id(category_id)
    if not category:
        return validation_error_response(
            message="Invalid category",
            errors={"category_id": "Category not found"}
        )
    
    if category.get("parent_id"):
        return validation_error_response(
            message="Invalid category",
            errors={"category_id": "Cannot use a subcategory as the main category"}
        )
    
    # Store category name for legacy compatibility
    category_name = category.get("name", "")
    
    # Validate subcategory if provided
    if subcategory_id:
        subcategory = await category_service.get_category_by_id(subcategory_id)
        if not subcategory:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory not found"}
            )
        if subcategory.get("parent_id") != category_id:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory doesn't belong to the selected category"}
            )
    
    # Validate tags (must be valid for the subcategory)
    validated_tags = []
    if tags.strip() and subcategory_id:
        valid_subcategory_tags = await tag_service.get_tags_by_subcategory(subcategory_id)
        
        submitted_tags = [t.strip() for t in tags.split(',') if t.strip()]
        submitted_tags = list(set(submitted_tags))[:10]  # Max 10 tags
        
        invalid_tags = []
        for tag_input in submitted_tags:
            tag_input_lower = tag_input.lower()
            matched_tag = None
            for tag in valid_subcategory_tags:
                if tag["slug"] == tag_input or tag["name"].lower() == tag_input_lower:
                    matched_tag = tag
                    break
            
            if matched_tag:
                validated_tags.append(matched_tag["slug"])
            else:
                invalid_tags.append(f"'{tag_input}' is not valid for this subcategory")
        
        if invalid_tags:
            return validation_error_response(
                message="Invalid tags provided",
                errors={"tags": invalid_tags}
            )
    elif tags.strip() and not subcategory_id:
        return validation_error_response(
            message="Subcategory required for tags",
            errors={"subcategory_id": "Please select a subcategory to use tags"}
        )
    user_id = str(current_user["_id"])
    
    # ==========================================
    # CREDIT VALIDATION (Dynamic from DB)
    # ==========================================
    contest_fee_service = ContestFeeService(db)
    
    # Validate contest creation requirements (balance, limits, etc.)
    validation = await contest_fee_service.validate_contest_creation(
        user_id=user_id,
        prize_pool=total_prize,
        max_participants=max_participants
    )
    
    if not validation.can_create:
        return error_response(
            message=validation.reason,
            status_code=400
        )
    
    # Handle cover image
    cover_image_url = None
    if cover_image and cover_image.filename:
        try:
            file_service = FileUploadService()
            file_info = await file_service.save_file(cover_image, user_id)
            cover_image_url = file_info["file_url"]
        except ValueError as e:
            return validation_error_response(errors={"cover_image": str(e)})
    
    # Create contest data
    contest_service = ContestService(db)
    
    contest_data = ContestCreate(
        title=title,
        description=description,
        category_id=category_id,
        subcategory_id=subcategory_id,
        tags=validated_tags,
        category=category_name,  # Legacy field for backward compatibility
        difficulty=difficulty,
        contest_type=ContestType.INDIVIDUAL,  # Always individual (team not supported yet)
        total_prize=total_prize,
        max_participants=max_participants,
        start_date=start_dt,
        end_date=end_dt,
        rules=rules
    )
    
    # First create the contest (we need the ID for payment reference)
    contest = await contest_service.create_contest(
        contest_data=contest_data,
        owner_id=user_id,
        owner_name=current_user.get("full_name") or current_user.get("email"),
        cover_image=cover_image_url
    )
    
    if not contest:
        return error_response(message="Failed to create contest")
    
    contest_id = str(contest["_id"])
    
    # ==========================================
    # PROCESS CREDIT PAYMENT
    # Lock prize pool + Deduct platform fee
    # ==========================================
    payment_success, payment_message, payment_details = await contest_fee_service.process_contest_creation_payment(
        user_id=user_id,
        contest_id=contest_id,
        contest_title=title,
        prize_pool=total_prize
    )
    
    if not payment_success:
        # Rollback: Delete the contest if payment fails
        await contest_service.contests.delete_one({"_id": contest["_id"]})
        return error_response(
            message=f"Contest creation failed: {payment_message}",
            status_code=400
        )
    
    # Update contest with payment info
    fee_info = validation.fee_breakdown
    await contest_service.contests.update_one(
        {"_id": contest["_id"]},
        {"$set": {
            "prize_pool_locked": True,
            "platform_fee": fee_info.platform_fee_total if fee_info else 0,
            "total_charged": fee_info.total_required if fee_info else total_prize,
            "payment_details": payment_details,
            "credits_locked_at": datetime.utcnow()
        }}
    )
    
    # Add payment info to response
    contest["prize_pool_locked"] = True
    contest["platform_fee"] = fee_info.platform_fee_total if fee_info else 0
    contest["total_charged"] = fee_info.total_required if fee_info else total_prize
    
    return success_response(
        message="Contest created successfully. Prize pool locked and platform fee charged.",
        data={
            "contest": convert_contest_to_json(contest),
            "payment": {
                "prize_pool": total_prize,
                "platform_fee": fee_info.platform_fee_total if fee_info else 0,
                "total_charged": fee_info.total_required if fee_info else total_prize,
                "credits_locked": True
            }
        },
        status_code=201
    )


# ==========================================
# CONTEST FEE ENDPOINTS (Dynamic from DB)
# ==========================================

@router.get("/fees/config")
async def get_contest_fee_config():
    """
    Get contest creation fee configuration.
    
    All settings are dynamic from database - no hardcoded values.
    Use this to display fee information to users before contest creation.
    """
    from app.services.contest.contest_fee import ContestFeeService
    
    db = Database.get_db()
    fee_service = ContestFeeService(db)
    config = await fee_service.get_config()
    
    return success_response(
        message="Fee configuration retrieved",
        data={"config": config}
    )


@router.get("/fees/calculate")
async def calculate_contest_fees(
    prize_pool: float = Query(..., gt=0, description="Prize pool amount in credits"),
    max_participants: int = Query(..., gt=0, description="Maximum participants"),
    current_user: dict = Depends(get_current_user)
):
    """
    Calculate fees for creating a contest (preview before actual creation).
    
    Returns:
    - Platform fee breakdown
    - Total credits required
    - Whether user can create this contest
    """
    from app.services.contest.contest_fee import ContestFeeService
    
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    fee_service = ContestFeeService(db)
    user_id = str(current_user["_id"])
    
    # Validate and calculate
    validation = await fee_service.validate_contest_creation(
        user_id=user_id,
        prize_pool=prize_pool,
        max_participants=max_participants
    )
    
    fee_calc = await fee_service.calculate_creation_fee(prize_pool)
    
    return success_response(
        message="Fee calculation complete",
        data={
            "can_create": validation.can_create,
            "reason": validation.reason,
            "fee_breakdown": {
                "prize_pool": fee_calc.prize_pool,
                "platform_fee_percentage": fee_calc.platform_fee_percentage,
                "platform_fee_fixed": fee_calc.platform_fee_fixed,
                "platform_fee_total": fee_calc.platform_fee_total,
                "total_required": fee_calc.total_required,
                "currency": fee_calc.currency
            },
            "user_balance": validation.user_balance,
            "active_contests": validation.active_contests
        }
    )


@router.get("")
async def get_contests(
    status: Optional[ContestStatus] = Query(None),
    category_id: Optional[str] = Query(None, description="Filter by main category ID"),
    subcategory_id: Optional[str] = Query(None, description="Filter by subcategory ID"),
    tag: Optional[str] = Query(None, description="Filter by tag slug"),
    # Legacy parameter for backward compatibility
    category: Optional[str] = Query(None, description="Legacy: Filter by category name"),
    difficulty: Optional[ContestDifficulty] = Query(None),
    visibility: str = Query("public", pattern="^(public|all)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get all contests with filtering.
    
    Filter parameters:
    - category_id: Filter by main category ID
    - subcategory_id: Filter by subcategory ID
    - tag: Filter by tag slug
    - category: Legacy filter by category name (deprecated, use category_id)
    
    Visibility modes:
    - public (default): Only shows published contests (UPCOMING, ACTIVE, JUDGING, COMPLETED)
    - all: Shows all contests (admin only - not implemented, defaults to public)
    
    Public users can NEVER see:
    - DRAFT contests
    - CANCELLED contests
    - Contests where is_active = False
    """
    db = Database.get_db()
    contest_service = ContestService(db)
    
    user_id = str(current_user["_id"]) if current_user else None
    
    contests, total = await contest_service.get_contests(
        status=status,
        category_id=category_id,
        subcategory_id=subcategory_id,
        tag=tag,
        category=category,  # Legacy support
        difficulty=difficulty,
        page=page,
        limit=limit,
        user_id=user_id,
        visibility=visibility
    )
    
    # Convert to JSON
    contests_data = [convert_contest_to_json(c) for c in contests]
    
    # Count by status (only public-visible contests)
    # Active statuses require is_active=True, completed doesn't
    active_base_filter = {"owner_id": {"$exists": True}, "is_active": True}
    
    upcoming_count = await db.contests.count_documents({
        **active_base_filter,
        "status": ContestStatus.UPCOMING.value
    })
    active_count = await db.contests.count_documents({
        **active_base_filter,
        "status": ContestStatus.ACTIVE.value
    })
    judging_count = await db.contests.count_documents({
        **active_base_filter,
        "status": ContestStatus.JUDGING.value
    })
    # Completed contests are visible regardless of is_active
    completed_count = await db.contests.count_documents({
        "owner_id": {"$exists": True},
        "status": ContestStatus.COMPLETED.value
    })
    
    return success_response(
        message="Contests retrieved successfully",
        data={
            "contests": contests_data,
            "counts": {
                "upcoming": upcoming_count,
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
    category_id: Optional[str] = Form(None, description="Main category ID"),
    subcategory_id: Optional[str] = Form(None, description="Subcategory ID"),
    tags: Optional[str] = Form(None, description="Comma-separated tag slugs"),
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
    - category_id, subcategory_id, tags follow the same validation as create
    """
    from app.services.forum.category import CategoryService
    from app.services.forum.tag import TagService
    
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
    category_service = CategoryService(db)
    tag_service = TagService(db)
    
    # Get existing contest for validation
    existing_contest = await contest_service.get_contest_by_id(contest_id)
    if not existing_contest:
        return error_response(message="Contest not found", status_code=404)
    
    # Determine effective category and subcategory IDs
    effective_category_id = category_id or existing_contest.get("category_id")
    effective_subcategory_id = subcategory_id or existing_contest.get("subcategory_id")
    
    category_name = None
    
    # Validate category if provided
    if category_id:
        category = await category_service.get_category_by_id(category_id)
        if not category:
            return validation_error_response(
                message="Invalid category",
                errors={"category_id": "Category not found"}
            )
        if category.get("parent_id"):
            return validation_error_response(
                message="Invalid category",
                errors={"category_id": "Cannot use a subcategory as the main category"}
            )
        category_name = category.get("name", "")
    
    # Validate subcategory if provided
    if subcategory_id:
        subcategory = await category_service.get_category_by_id(subcategory_id)
        if not subcategory:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory not found"}
            )
        if subcategory.get("parent_id") != effective_category_id:
            return validation_error_response(
                message="Invalid subcategory",
                errors={"subcategory_id": "Subcategory doesn't belong to the selected category"}
            )
    
    # Validate tags if provided
    validated_tags = None
    if tags is not None:
        if tags.strip() and effective_subcategory_id:
            valid_subcategory_tags = await tag_service.get_tags_by_subcategory(effective_subcategory_id)
            
            submitted_tags = [t.strip() for t in tags.split(',') if t.strip()]
            submitted_tags = list(set(submitted_tags))[:10]
            
            validated_tags = []
            invalid_tags = []
            for tag_input in submitted_tags:
                tag_input_lower = tag_input.lower()
                matched_tag = None
                for tag in valid_subcategory_tags:
                    if tag["slug"] == tag_input or tag["name"].lower() == tag_input_lower:
                        matched_tag = tag
                        break
                
                if matched_tag:
                    validated_tags.append(matched_tag["slug"])
                else:
                    invalid_tags.append(f"'{tag_input}' is not valid for this subcategory")
            
            if invalid_tags:
                return validation_error_response(
                    message="Invalid tags provided",
                    errors={"tags": invalid_tags}
                )
        elif tags.strip() and not effective_subcategory_id:
            return validation_error_response(
                message="Subcategory required for tags",
                errors={"subcategory_id": "Please select a subcategory to use tags"}
            )
        else:
            validated_tags = []  # Empty tags
    
    update_data = ContestUpdate(
        title=title,
        description=description,
        category_id=category_id,
        subcategory_id=subcategory_id,
        tags=validated_tags,
        category=category_name,  # Legacy field
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


@router.post("/{contest_identifier}/publish")
async def publish_contest(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Publish a contest (DRAFT -> UPCOMING).
    
    Makes the contest visible to the public.
    Users can join after publishing.
    Contest will auto-start at start_date.
    
    Requirements:
    - Must be in DRAFT status
    - Must have at least 1 task
    - start_date must be in the future
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
    
    success, message = await contest_service.publish_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"published": True, "status": "upcoming"}
    )


@router.post("/{contest_identifier}/cancel")
async def cancel_contest(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a contest (DRAFT/UPCOMING -> CANCELLED).
    
    Only allowed if:
    - Contest is in DRAFT or UPCOMING status
    - No participants have joined
    
    If prize pool was locked, it will be refunded (minus cancellation fee if applicable).
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
    
    success, message, refund_details = await contest_service.cancel_contest(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={
            "cancelled": True,
            "status": "cancelled",
            "refund": refund_details
        }
    )


@router.post("/{contest_identifier}/complete")
async def complete_contest(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Complete a contest (ACTIVE/JUDGING -> COMPLETED).
    
    Requirements:
    - Must be in ACTIVE or JUDGING status
    - Must have at least 1 participant
    - Must have at least 1 submission
    - Must have at least 1 approved submission
    
    Actions:
    - Calculates final weighted scores
    - Distributes prizes to winners
    - Marks contest as completed
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
    
    # Check if contest can be completed
    contest = await contest_service.contests.find_one({"_id": ObjectId(contest_id)})
    if not contest:
        return error_response(message="Contest not found", status_code=404)
    
    # Verify ownership
    if str(contest["owner_id"]) != str(current_user["_id"]):
        return error_response(message="Only contest owner can complete", status_code=403)
    
    # Validate can complete
    can_comp, reason, stats = await contest_service.can_complete(contest)
    if not can_comp:
        # Include stats in the message for better context
        if stats:
            reason = f"{reason} (participants: {stats.get('participants', 0)}, submissions: {stats.get('submissions', 0)}, approved: {stats.get('approved', 0)})"
        return error_response(
            message=reason,
            status_code=400
        )
    
    # Distribute prizes
    from app.services.contest.prize_distribution import PrizeDistributionService
    prize_service = PrizeDistributionService(db)
    
    dist_success, dist_message, distribution = await prize_service.distribute_prizes(
        contest_id=contest_id,
        owner_id=str(current_user["_id"]),
        distribution_mode="proportional"
    )
    
    if not dist_success:
        return error_response(message=f"Prize distribution failed: {dist_message}", status_code=400)
    
    # Update contest status
    from datetime import datetime
    await contest_service.contests.update_one(
        {"_id": ObjectId(contest_id)},
        {"$set": {
            "status": ContestStatus.COMPLETED,
            "completed_at": datetime.utcnow(),
            "auto_completed": False,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return success_response(
        message="Contest completed successfully. Prizes distributed.",
        data={
            "completed": True,
            "status": "completed",
            "distribution": distribution
        }
    )


@router.get("/{contest_identifier}/scores")
async def get_contest_scores(
    contest_identifier: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get weighted scores for all participants.
    
    Returns participants ranked by weighted score with:
    - Rank
    - Weighted score
    - Task-by-task breakdown
    - Approved tasks count
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    from app.services.contest.scoring import ScoringService
    scoring_service = ScoringService(db)
    
    leaderboard, total = await scoring_service.get_leaderboard(
        contest_id=contest_id,
        page=page,
        limit=limit
    )
    
    return success_response(
        message="Scores retrieved successfully",
        data={
            "scores": leaderboard,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@router.get("/{contest_identifier}/prize-distribution")
async def get_prize_distribution_preview(
    contest_identifier: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Preview prize distribution for the contest.
    
    Shows how prizes would be distributed based on current scores.
    If authenticated, shows user's position.
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    from app.services.contest.prize_distribution import PrizeDistributionService
    prize_service = PrizeDistributionService(db)
    
    user_id = str(current_user["_id"]) if current_user else None
    
    preview = await prize_service.get_distribution_preview(
        contest_id=contest_id,
        user_id=user_id
    )
    
    if "error" in preview:
        return error_response(message=preview["error"], status_code=400)
    
    return success_response(
        message="Prize distribution preview",
        data=preview
    )


@router.get("/{contest_identifier}/task-winners")
async def get_task_wise_winners(
    contest_identifier: str
):
    """
    Get winners for each task in the contest.
    
    Returns all tasks with their top performers ranked by submission score.
    Useful for:
    - Showing task-by-task breakdown
    - Highlighting best performers per task
    - Detailed scoring analysis
    
    Each task includes:
    - Task info (title, points, weightage)
    - Submission counts
    - Ranked list of approved submissions with scores
    - Top winner highlighted
    """
    try:
        db = Database.get_db()
        
        # Resolve contest identifier to ID
        contest_id = await resolve_contest_id(contest_identifier, db)
        if not contest_id:
            return error_response(message="Contest not found", status_code=404)
        
        from app.services.contest.scoring import ScoringService
        scoring_service = ScoringService(db)
        
        task_winners = await scoring_service.get_task_wise_winners(contest_id)
        
        # Convert datetime to ISO format for JSON serialization (if not already string)
        from datetime import datetime as dt
        for task in task_winners:
            for winner in task.get("winners", []):
                if winner.get("submitted_at") and isinstance(winner["submitted_at"], dt):
                    winner["submitted_at"] = winner["submitted_at"].isoformat()
                if winner.get("approved_at") and isinstance(winner["approved_at"], dt):
                    winner["approved_at"] = winner["approved_at"].isoformat()
            if task.get("top_winner"):
                if task["top_winner"].get("submitted_at") and isinstance(task["top_winner"]["submitted_at"], dt):
                    task["top_winner"]["submitted_at"] = task["top_winner"]["submitted_at"].isoformat()
                if task["top_winner"].get("approved_at") and isinstance(task["top_winner"]["approved_at"], dt):
                    task["top_winner"]["approved_at"] = task["top_winner"]["approved_at"].isoformat()
        
        return success_response(
            message="Task-wise winners retrieved successfully",
            data={
                "tasks": task_winners,
                "total_tasks": len(task_winners),
                "summary": {
                    "tasks_with_winners": sum(1 for t in task_winners if t.get("top_winner")),
                    "total_approved_submissions": sum(t.get("approved_submissions", 0) for t in task_winners)
                }
            }
        )
    except Exception as e:
        import traceback
        print(f"[ERROR] get_task_wise_winners: {str(e)}")
        traceback.print_exc()
        return error_response(message=f"Error retrieving task winners: {str(e)}", status_code=500)


@router.get("/{contest_identifier}/tasks/{task_id}/leaderboard")
async def get_task_leaderboard(
    contest_identifier: str,
    task_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get leaderboard for a specific task.
    
    Shows all approved submissions for the task ranked by score.
    Useful for detailed task-level competition view.
    """
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    from app.services.contest.scoring import ScoringService
    scoring_service = ScoringService(db)
    
    leaderboard, total, task_info = await scoring_service.get_task_leaderboard(
        contest_id=contest_id,
        task_id=task_id,
        page=page,
        limit=limit
    )
    
    if not task_info:
        return error_response(message="Task not found", status_code=404)
    
    # Convert datetime to ISO format (if not already string)
    from datetime import datetime as dt
    for entry in leaderboard:
        if entry.get("submitted_at") and isinstance(entry["submitted_at"], dt):
            entry["submitted_at"] = entry["submitted_at"].isoformat()
        if entry.get("approved_at") and isinstance(entry["approved_at"], dt):
            entry["approved_at"] = entry["approved_at"].isoformat()
    
    return success_response(
        message="Task leaderboard retrieved successfully",
        data={
            "task": task_info,
            "leaderboard": leaderboard,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
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
    
    # Convert to JSON-serializable format
    participants_data = []
    for p in participants:
        p["id"] = str(p["_id"])
        del p["_id"]
        # Convert all datetime fields
        for key, value in list(p.items()):
            if isinstance(value, datetime):
                p[key] = value.isoformat()
            elif isinstance(value, ObjectId):
                p[key] = str(value)
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


# ============================================================================
# SCHEDULER / SYSTEM ENDPOINTS
# ============================================================================

@router.get("/system/scheduler-status")
async def get_scheduler_status():
    """
    Get contest scheduler status (for monitoring).
    
    Shows:
    - Scheduler running status
    - Configured jobs and next run times
    - Recent job execution stats
    """
    try:
        from app.core.scheduler import get_scheduler_status as get_status
        status = get_status()
        return success_response(
            message="Scheduler status retrieved",
            data=status
        )
    except ImportError:
        return error_response(
            message="Scheduler not available",
            status_code=503
        )


@router.post("/system/run-scheduler")
async def run_scheduler_manually(
    current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger all scheduler jobs (admin only - for testing).
    
    Runs:
    - auto_start_contests
    - transition_to_judging
    - auto_complete_contests
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # TODO: Add admin check here
    
    try:
        db = Database.get_db()
        from app.services.scheduler.contest_scheduler import ContestScheduler
        
        scheduler = ContestScheduler(db)
        results = await scheduler.run_all_jobs()
        
        return success_response(
            message="Scheduler jobs executed",
            data=results
        )
    except Exception as e:
        return error_response(
            message=f"Scheduler execution failed: {str(e)}",
            status_code=500
        )
