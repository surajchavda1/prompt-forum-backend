from fastapi import APIRouter, Query, Depends
from app.database import Database
from app.services.contest.leaderboard import LeaderboardService
from app.routes.auth.dependencies import get_current_user
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@router.get("")
async def get_global_leaderboard(
    limit: int = Query(10, ge=1, le=100, description="Number of top users to return"),
    time_period: str = Query("all_time", regex="^(all_time|this_month|this_week|today)$")
):
    """
    Get global leaderboard with real reputation rankings.
    
    Calculates from database in real-time:
    - Reputation: Post upvotes (+10), Answer upvotes (+10), Accepted (+15)
    - Total answers: Count from database
    - Acceptance rate: (accepted / total) * 100
    - Earnings: Sum from contest winnings
    - Rank badge: Based on reputation tier
    
    Time periods:
    - all_time: All contributions
    - this_month: Current month only
    - this_week: Current week only
    - today: Today only
    
    NO MOCK DATA - all calculations from actual database.
    """
    db = Database.get_db()
    leaderboard_service = LeaderboardService(db)
    
    top_contributors = await leaderboard_service.get_top_contributors(
        limit=limit,
        time_period=time_period
    )
    
    return success_response(
        message="Leaderboard retrieved successfully",
        data={
            "leaderboard": top_contributors,
            "total_users": len(top_contributors),
            "time_period": time_period
        }
    )


@router.get("/{user_id}/rank")
async def get_user_rank(user_id: str):
    """
    Get specific user's global rank and complete stats.
    
    Returns:
    - Global rank position
    - Reputation points
    - Total answers
    - Acceptance rate
    - Total earnings
    - Rank badge (Grandmaster, Master, Expert, etc.)
    - Trend indicator
    """
    db = Database.get_db()
    leaderboard_service = LeaderboardService(db)
    
    rank_info = await leaderboard_service.get_user_rank(user_id)
    
    return success_response(
        message="User rank retrieved successfully",
        data=rank_info
    )


@router.get("/me/rank")
async def get_my_rank(current_user: dict = Depends(get_current_user)):
    """
    Get current logged-in user's rank.
    
    Convenience endpoint for "Your Ranking" card.
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    leaderboard_service = LeaderboardService(db)
    
    rank_info = await leaderboard_service.get_user_rank(str(current_user["_id"]))
    
    # Add user's name
    rank_info["user_name"] = current_user.get("full_name", current_user.get("email", "").split("@")[0])
    
    return success_response(
        message="Your rank retrieved successfully",
        data=rank_info
    )
