"""
Prize Distribution Service

Handles the distribution of prizes to contest winners based on weighted scores.

Distribution Formula:
- Participant Share = (Participant Score / Total Scores) × Prize Pool

Features:
- Performance-based distribution
- Winner-takes-all option
- Proportional split option
- Transaction tracking
- Rollback support
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from bson import ObjectId

from app.services.contest.scoring import ScoringService
from app.models.payment.transaction import TransactionCategory
from app.utils.wallet import WalletUtils


class PrizeDistributionService:
    """
    Service for distributing contest prizes to winners.
    
    Distribution Modes:
    1. Proportional (default): Prize split by score ratio
    2. Winner-takes-all: Top scorer gets 100%
    3. Tiered: Predefined percentages for ranks (future)
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.contests = db.contests
        self.participants = db.contest_participants
        self.submissions = db.contest_submissions
        self.scoring_service = ScoringService(db)
        self.wallet_utils = WalletUtils(db)
    
    async def calculate_distribution(
        self,
        contest_id: str,
        distribution_mode: str = "proportional"  # proportional, winner_takes_all
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Calculate prize distribution without executing.
        
        Use this for preview before actual distribution.
        
        Returns: (success, message, distribution_list)
        """
        try:
            # Get contest
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            if not contest:
                return False, "Contest not found", []
            
            prize_pool = contest.get("total_prize", 0)
            if prize_pool <= 0:
                return False, "No prize pool available", []
            
            # Calculate final scores for all participants
            await self.scoring_service.update_all_participant_scores(contest_id)
            
            # Get prize shares
            prize_shares = await self.scoring_service.calculate_prize_shares(
                contest_id, prize_pool
            )
            
            if not prize_shares:
                return False, "No eligible winners found (no approved submissions)", []
            
            if distribution_mode == "winner_takes_all":
                # Top scorer gets everything
                if prize_shares:
                    winner = prize_shares[0]
                    return True, "Distribution calculated (winner takes all)", [{
                        "user_id": winner["user_id"],
                        "username": winner["username"],
                        "rank": 1,
                        "weighted_score": winner["weighted_score"],
                        "score_percentage": 100.0,
                        "prize_amount": prize_pool
                    }]
            
            # Proportional distribution (default)
            return True, "Distribution calculated", prize_shares
            
        except Exception as e:
            print(f"Error calculating distribution: {str(e)}")
            return False, f"Calculation failed: {str(e)}", []
    
    async def distribute_prizes(
        self,
        contest_id: str,
        owner_id: str,
        distribution_mode: str = "proportional"
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Execute prize distribution to winners.
        
        Flow:
        1. Validate contest can be completed
        2. ATOMIC: Set distribution_in_progress flag (prevents race condition)
        3. Calculate final scores
        4. Calculate prize shares
        5. Unlock prize pool from owner
        6. Deduct from owner
        7. Credit each winner
        8. Update participant records
        9. Log all transactions
        
        Returns: (success, message, distribution_details)
        """
        try:
            # ATOMIC: Try to acquire distribution lock
            # This prevents race condition between manual distribution and scheduler
            lock_result = await self.contests.update_one(
                {
                    "_id": ObjectId(contest_id),
                    "prizes_distributed": {"$ne": True},
                    "distribution_in_progress": {"$ne": True}
                },
                {
                    "$set": {
                        "distribution_in_progress": True,
                        "distribution_started_at": datetime.utcnow()
                    }
                }
            )
            
            if lock_result.modified_count == 0:
                # Either already distributed or another process is distributing
                contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
                if contest and contest.get("prizes_distributed", False):
                    return False, "Prizes have already been distributed", None
                if contest and contest.get("distribution_in_progress", False):
                    return False, "Prize distribution is already in progress", None
                return False, "Contest not found or cannot distribute", None
            
            # Now we have the lock, get contest details
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            if not contest:
                return False, "Contest not found", None
            
            # Verify owner
            if str(contest["owner_id"]) != owner_id:
                # Release lock
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {"distribution_in_progress": False}}
                )
                return False, "Only contest owner can distribute prizes", None
            
            prize_pool = contest.get("total_prize", 0)
            contest_title = contest.get("title", "Unknown Contest")
            
            # Helper to release lock on failure
            async def release_lock():
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {"distribution_in_progress": False}}
                )
            
            if prize_pool <= 0:
                await release_lock()
                return False, "No prize pool available", None
            
            # Calculate distribution
            success, message, distribution = await self.calculate_distribution(
                contest_id, distribution_mode
            )
            
            if not success:
                await release_lock()
                return False, message, None
            
            if not distribution:
                await release_lock()
                return False, "No eligible winners to distribute prizes to", None
            
            # Start distribution process
            distribution_results = {
                "contest_id": contest_id,
                "prize_pool": prize_pool,
                "distribution_mode": distribution_mode,
                "winners": [],
                "total_distributed": 0,
                "distributed_at": datetime.utcnow().isoformat()
            }
            
            # Unlock prize pool from owner's locked balance
            unlock_success, unlock_message = await self.wallet_utils.unlock_balance(
                user_id=owner_id,
                amount=prize_pool,
                reason=f"Prize distribution for contest: {contest_title}",
                reference_type="contest_prize",
                reference_id=contest_id
            )
            
            if not unlock_success:
                print(f"[WARN] Failed to unlock prize pool: {unlock_message}")
                # Continue anyway - funds might already be unlocked
            
            # Deduct prize pool from owner (idempotent - safe to retry)
            deduct_success, deduct_message, _ = await self.wallet_utils.deduct_balance(
                user_id=owner_id,
                amount=prize_pool,
                category=TransactionCategory.CONTEST_ENTRY,  # Using CONTEST_ENTRY for outflow
                description=f"Prize pool distribution for contest: {contest_title}",
                reference_type="contest_prize_distribution",
                reference_id=contest_id,
                idempotency_key=f"PRIZE_DIST_{contest_id}"
            )
            
            if not deduct_success:
                await release_lock()
                return False, f"Failed to deduct prize pool from owner: {deduct_message}", None
            
            # Credit each winner (idempotent - safe to retry)
            failed_credits = []
            for winner in distribution:
                credit_success, credit_message, txn = await self.wallet_utils.add_balance(
                    user_id=winner["user_id"],
                    amount=winner["prize_amount"],
                    category=TransactionCategory.CONTEST_PRIZE,
                    description=f"Contest prize (Rank #{winner['rank']}) - {contest_title}",
                    reference_type="contest_prize",
                    reference_id=contest_id,
                    idempotency_key=f"PRIZE_{contest_id}_{winner['user_id']}"
                )
                
                if not credit_success:
                    failed_credits.append({
                        "user_id": winner["user_id"],
                        "amount": winner["prize_amount"],
                        "error": credit_message
                    })
                    print(f"[ERROR] Failed to credit winner {winner['user_id']}: {credit_message}")
                
                # Update participant record
                now = datetime.utcnow()
                await self.participants.update_one(
                    {"contest_id": contest_id, "user_id": winner["user_id"]},
                    {"$set": {
                        "earnings": winner["prize_amount"],
                        "prize_distributed": credit_success,
                        "prize_distributed_at": now if credit_success else None,
                        "final_rank": winner["rank"],
                        "credit_failed": not credit_success,
                        "credit_error": credit_message if not credit_success else None
                    }}
                )
                
                distribution_results["winners"].append({
                    "user_id": winner["user_id"],
                    "username": winner["username"],
                    "rank": winner["rank"],
                    "weighted_score": winner["weighted_score"],
                    "score_percentage": winner["score_percentage"],
                    "prize_amount": winner["prize_amount"],
                    "credit_success": credit_success,
                    "transaction_id": txn.get("transaction_id") if txn else None,
                    "error": credit_message if not credit_success else None
                })
                
                if credit_success:
                    distribution_results["total_distributed"] += winner["prize_amount"]
            
            # Mark contest as COMPLETED with prizes distributed
            from app.models.contest.contest import ContestStatus
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": {
                    "status": ContestStatus.COMPLETED,
                    "completed_at": datetime.utcnow(),
                    "prizes_distributed": True,
                    "prizes_distributed_at": datetime.utcnow(),
                    "distribution_in_progress": False,  # Release lock
                    "distribution_details": distribution_results,
                    "prize_pool_locked": False,
                    "is_active": False,  # No longer joinable
                    "failed_credits": failed_credits if failed_credits else None
                }}
            )
            
            if failed_credits:
                print(f"[WARN] Prize distribution completed with {len(failed_credits)} failed credits for contest {contest_id}")
                return True, f"Prizes distributed with {len(failed_credits)} failures (will retry)", distribution_results
            
            print(f"[OK] Prize distribution completed for contest {contest_id}: "
                  f"{len(distribution)} winners, total {distribution_results['total_distributed']}")
            
            return True, "Prizes distributed successfully", distribution_results
            
        except Exception as e:
            print(f"[ERROR] Prize distribution failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Distribution failed: {str(e)}", None
    
    async def get_distribution_preview(
        self,
        contest_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a preview of how prizes would be distributed.
        
        Useful for showing participants their potential earnings.
        """
        contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
        if not contest:
            return {"error": "Contest not found"}
        
        prize_pool = contest.get("total_prize", 0)
        
        # Calculate distribution
        success, message, distribution = await self.calculate_distribution(contest_id)
        
        if not success:
            return {"error": message, "prize_pool": prize_pool}
        
        result = {
            "contest_id": contest_id,
            "prize_pool": prize_pool,
            "total_winners": len(distribution),
            "distribution": distribution,
            "is_preview": True
        }
        
        # If user_id provided, highlight their position
        if user_id:
            user_position = next(
                (d for d in distribution if d["user_id"] == user_id),
                None
            )
            result["user_position"] = user_position
        
        return result
    
    async def process_no_submission_refund(
        self,
        contest_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Process full refund when contest ends with no submissions.
        
        This protects the owner when no work is delivered.
        
        Conditions:
        - Contest ended (end_date passed)
        - No submissions made OR no submissions approved
        
        Returns: (success, message, refund_details)
        """
        try:
            # ATOMIC: Try to acquire refund lock (prevents race condition)
            lock_result = await self.contests.update_one(
                {
                    "_id": ObjectId(contest_id),
                    "refund_processed": {"$ne": True},
                    "prizes_distributed": {"$ne": True},
                    "refund_in_progress": {"$ne": True}
                },
                {
                    "$set": {
                        "refund_in_progress": True,
                        "refund_started_at": datetime.utcnow()
                    }
                }
            )
            
            if lock_result.modified_count == 0:
                contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
                if contest and contest.get("refund_processed", False):
                    return False, "Refund has already been processed", None
                if contest and contest.get("prizes_distributed", False):
                    return False, "Cannot refund: prizes already distributed", None
                if contest and contest.get("refund_in_progress", False):
                    return False, "Refund is already in progress", None
                return False, "Contest not found or cannot process refund", None
            
            contest = await self.contests.find_one({"_id": ObjectId(contest_id)})
            if not contest:
                return False, "Contest not found", None
            
            owner_id = contest["owner_id"]
            prize_pool = contest.get("total_prize", 0)
            contest_title = contest.get("title", "Unknown")
            
            # Helper to release lock on failure
            async def release_lock():
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {"refund_in_progress": False}}
                )
            
            # Check submission status
            submission_count = await self.submissions.count_documents({
                "contest_id": contest_id
            })
            
            approved_count = await self.submissions.count_documents({
                "contest_id": contest_id,
                "status": "approved"
            })
            
            if approved_count > 0:
                await release_lock()
                return False, "Cannot refund: contest has approved submissions", None
            
            # Unlock prize pool (idempotent)
            unlock_success, unlock_message = await self.wallet_utils.unlock_balance(
                user_id=owner_id,
                amount=prize_pool,
                reason=f"No submission refund for contest: {contest_title}",
                reference_type="contest_prize",
                reference_id=contest_id
            )
            
            if not unlock_success:
                print(f"[WARN] Failed to unlock for refund: {unlock_message}")
            
            # Update contest - mark as COMPLETED with refund (also releases lock)
            from app.models.contest.contest import ContestStatus
            now = datetime.utcnow()
            await self.contests.update_one(
                {"_id": ObjectId(contest_id)},
                {"$set": {
                    "status": ContestStatus.COMPLETED,
                    "completed_at": now,
                    "is_active": False,
                    "prize_pool_locked": False,
                    "refund_processed": True,
                    "refund_in_progress": False,  # Release lock
                    "refund_processed_at": now,
                    "refund_reason": "no_submissions" if submission_count == 0 else "no_approved_submissions",
                    "refund_amount": prize_pool
                }}
            )
            
            refund_details = {
                "contest_id": contest_id,
                "owner_id": owner_id,
                "refund_amount": prize_pool,
                "reason": "No submissions" if submission_count == 0 else "No approved submissions",
                "submission_count": submission_count,
                "approved_count": approved_count,
                "processed_at": now.isoformat()
            }
            
            print(f"[OK] No-submission refund processed for contest {contest_id}: {prize_pool} credits")
            
            return True, "Refund processed successfully (100% - no platform fee)", refund_details
            
        except Exception as e:
            print(f"[ERROR] No-submission refund failed: {str(e)}")
            # Try to release lock on error
            try:
                await self.contests.update_one(
                    {"_id": ObjectId(contest_id)},
                    {"$set": {"refund_in_progress": False}}
                )
            except:
                pass
            return False, f"Refund failed: {str(e)}", None
