"""
User Contest Routes
Public endpoints for viewing user's contest participation and organization
"""
from fastapi import APIRouter, Query
from app.database import Database
from app.utils.response import success_response, error_response
from bson import ObjectId

router = APIRouter(prefix="/api/users", tags=["User Contests"])


@router.get("/{user_id}/contests")
async def get_user_contests(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get ALL contests for a user (both participated and organized).
    
    Convenience endpoint that returns both types of contests.
    Use this for a unified view of all user's contest activity.
    
    Public endpoint.
    
    Returns:
    - participated: List of contests user joined
    - organized: List of contests user created
    - statistics: Overall contest stats
    """
    try:
        db = Database.get_db()
        
        # Verify user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return error_response(
                message="User not found",
                status_code=404
            )
        
        # Get participated contests
        participant_query = {"user_id": user_id}
        participants = await db.contest_participants.find(
            participant_query
        ).to_list(length=None)
        
        participated_contests = []
        if participants:
            contest_ids = [ObjectId(p["contest_id"]) for p in participants]
            contests = await db.contests.find({
                "_id": {"$in": contest_ids},
                "owner_id": {"$exists": True}
            }).sort("created_at", -1).to_list(length=None)
            
            for contest in contests:
                contest_id = str(contest["_id"])
                participant = next(
                    (p for p in participants if p["contest_id"] == contest_id),
                    None
                )
                
                contest_json = convert_contest_to_json(contest)
                
                if participant:
                    contest_json["participation"] = {
                        "joined_at": participant.get("joined_at").isoformat() if participant.get("joined_at") else None,
                        "total_score": participant.get("total_score", 0),
                        "approved_tasks": participant.get("approved_tasks", 0),
                        "pending_tasks": participant.get("pending_tasks", 0)
                    }
                
                participated_contests.append(contest_json)
        
        # Get organized contests
        organized_contests_data = await db.contests.find({
            "owner_id": user_id
        }).sort("created_at", -1).to_list(length=None)
        
        organized_contests = []
        for contest in organized_contests_data:
            contest_id = str(contest["_id"])
            
            # Get stats
            participant_count = await db.contest_participants.count_documents({
                "contest_id": contest_id
            })
            submission_count = await db.contest_submissions.count_documents({
                "contest_id": contest_id
            })
            task_count = await db.contest_tasks.count_documents({
                "contest_id": contest_id
            })
            
            contest_json = convert_contest_to_json(contest)
            contest_json["organizer_stats"] = {
                "total_participants": participant_count,
                "total_submissions": submission_count,
                "total_tasks": task_count
            }
            
            organized_contests.append(contest_json)
        
        # Get statistics
        total_earnings = sum(p.get("earnings", 0) for p in participants)
        
        return success_response(
            message="User contests retrieved successfully",
            data={
                "participated": participated_contests,
                "organized": organized_contests,
                "statistics": {
                    "participated_count": len(participated_contests),
                    "organized_count": len(organized_contests),
                    "total_earnings": total_earnings
                }
            }
        )
        
    except Exception as e:
        print(f"Error getting user contests: {str(e)}")
        return error_response(
            message=f"Failed to retrieve contests: {str(e)}",
            status_code=500
        )


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


@router.get("/{user_id}/contests/participated")
async def get_user_participated_contests(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query(None, pattern="^(active|completed|all)$")
):
    """
    Get all contests a user has participated in.
    
    Public endpoint - shows contest participation history.
    
    Parameters:
    - user_id: User's ID
    - page: Page number
    - limit: Results per page
    - status: Filter by status (active, completed, all)
    
    Returns:
    - List of contests user joined
    - Participation stats for each contest
    """
    try:
        db = Database.get_db()
        
        # Verify user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return error_response(
                message="User not found",
                status_code=404
            )
        
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
            "owner_id": {"$exists": True}  # Filter out malformed data
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
                    "rank": None  # Will calculate if needed
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
            message="Participated contests retrieved successfully",
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
        print(f"Error getting participated contests: {str(e)}")
        return error_response(
            message=f"Failed to retrieve participated contests: {str(e)}",
            status_code=500
        )


@router.get("/{user_id}/contests/organized")
async def get_user_organized_contests(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query(None, pattern="^(draft|active|completed|all)$")
):
    """
    Get all contests organized/created by a user.
    
    Public endpoint - shows user's contest creation history.
    
    Parameters:
    - user_id: User's ID
    - page: Page number
    - limit: Results per page
    - status: Filter by status (draft, active, completed, all)
    
    Returns:
    - List of contests user created
    - Statistics for each contest
    """
    try:
        db = Database.get_db()
        
        # Verify user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return error_response(
                message="User not found",
                status_code=404
            )
        
        # Build query
        contest_query = {
            "owner_id": user_id
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
        
        # Enrich with statistics
        contests_data = []
        for contest in contests:
            contest_id = str(contest["_id"])
            
            # Get participant count
            participant_count = await db.contest_participants.count_documents({
                "contest_id": contest_id
            })
            
            # Get submission count
            submission_count = await db.contest_submissions.count_documents({
                "contest_id": contest_id
            })
            
            # Get task count
            task_count = await db.contest_tasks.count_documents({
                "contest_id": contest_id
            })
            
            contest_json = convert_contest_to_json(contest)
            
            # Add organizer statistics
            contest_json["organizer_stats"] = {
                "total_participants": participant_count,
                "total_submissions": submission_count,
                "total_tasks": task_count
            }
            
            contests_data.append(contest_json)
        
        total_pages = (total + limit - 1) // limit
        
        return success_response(
            message="Organized contests retrieved successfully",
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
        print(f"Error getting organized contests: {str(e)}")
        return error_response(
            message=f"Failed to retrieve organized contests: {str(e)}",
            status_code=500
        )


@router.get("/{user_id}/contests/statistics")
async def get_user_contest_statistics(user_id: str):
    """
    Get user's overall contest statistics.
    
    Public endpoint - shows contest performance summary.
    
    Returns:
    - Total contests participated
    - Total contests organized
    - Total earnings
    - Average rank
    - Win rate
    - Best rank achieved
    """
    try:
        db = Database.get_db()
        
        # Verify user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return error_response(
                message="User not found",
                status_code=404
            )
        
        # Get participation stats
        participated_count = await db.contest_participants.count_documents({
            "user_id": user_id
        })
        
        # Get organized count
        organized_count = await db.contests.count_documents({
            "owner_id": user_id
        })
        
        # Get all participations for detailed stats
        participants = await db.contest_participants.find({
            "user_id": user_id
        }).to_list(length=None)
        
        total_earnings = sum(p.get("earnings", 0) for p in participants)
        
        # Calculate average rank and best rank
        ranks = []
        for participant in participants:
            contest_id = participant["contest_id"]
            
            # Get user's rank in this contest
            all_participants = await db.contest_participants.find({
                "contest_id": contest_id
            }).sort("total_score", -1).to_list(length=None)
            
            for idx, p in enumerate(all_participants, 1):
                if p["user_id"] == user_id:
                    ranks.append(idx)
                    break
        
        average_rank = sum(ranks) / len(ranks) if ranks else None
        best_rank = min(ranks) if ranks else None
        
        # Count wins (rank 1)
        wins = sum(1 for r in ranks if r == 1)
        win_rate = (wins / len(ranks) * 100) if ranks else 0
        
        # Get total approved tasks
        total_approved = sum(p.get("approved_tasks", 0) for p in participants)
        
        return success_response(
            message="Contest statistics retrieved successfully",
            data={
                "statistics": {
                    "participated_count": participated_count,
                    "organized_count": organized_count,
                    "total_earnings": total_earnings,
                    "average_rank": round(average_rank, 1) if average_rank else None,
                    "best_rank": best_rank,
                    "wins": wins,
                    "win_rate": round(win_rate, 1),
                    "total_approved_tasks": total_approved
                }
            }
        )
        
    except Exception as e:
        print(f"Error getting contest statistics: {str(e)}")
        return error_response(
            message=f"Failed to retrieve statistics: {str(e)}",
            status_code=500
        )
