"""
Contest Scheduler Service

Handles automatic contest state transitions:
- Auto-start: UPCOMING -> ACTIVE when start_date is reached
- Auto-complete: ACTIVE -> COMPLETED when end_date + grace period is reached
- Refund processing: Full refund if no submissions at end

This ensures fair treatment of both owners and participants.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId

from app.models.contest.contest import ContestStatus
from app.models.contest.audit import AuditAction
from app.services.contest.audit import AuditService


class ContestScheduler:
    """
    Background job handler for contest lifecycle management.
    
    Jobs:
    1. auto_start_contests: Run every minute
    2. auto_complete_contests: Run every 5 minutes
    3. process_refunds: Run every 5 minutes (integrated with auto_complete)
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.contests = db.contests
        self.participants = db.contest_participants
        self.submissions = db.contest_submissions
        self.audit_service = AuditService(db)
    
    async def auto_start_contests(self) -> Dict[str, Any]:
        """
        Auto-start contests when start_date is reached.
        
        Conditions:
        - status = UPCOMING
        - is_active = True
        - start_date <= now
        
        Action:
        - Set status = ACTIVE
        """
        now = datetime.utcnow()
        results = {
            "processed": 0,
            "started": [],
            "errors": []
        }
        
        try:
            # Find contests ready to start
            contests_to_start = await self.contests.find({
                "status": ContestStatus.UPCOMING,
                "is_active": True,
                "start_date": {"$lte": now}
            }).to_list(length=100)
            
            for contest in contests_to_start:
                contest_id = str(contest["_id"])
                
                try:
                    # Update status to ACTIVE
                    await self.contests.update_one(
                        {"_id": contest["_id"]},
                        {"$set": {
                            "status": ContestStatus.ACTIVE,
                            "updated_at": now
                        }}
                    )
                    
                    # Get participant count for logging
                    participant_count = await self.participants.count_documents({
                        "contest_id": contest_id
                    })
                    
                    # Log to audit trail
                    await self.audit_service.log_action(
                        contest_id=contest_id,
                        action=AuditAction.CONTEST_STARTED,
                        user_id="system",
                        username="System Scheduler",
                        entity_type="contest",
                        entity_id=contest_id,
                        metadata={
                            "trigger": "auto_start",
                            "scheduled_start": contest["start_date"].isoformat(),
                            "actual_start": now.isoformat(),
                            "participant_count": participant_count
                        }
                    )
                    
                    results["started"].append({
                        "contest_id": contest_id,
                        "title": contest.get("title", "Unknown"),
                        "participants": participant_count
                    })
                    results["processed"] += 1
                    
                    print(f"[SCHEDULER] Auto-started contest: {contest_id} "
                          f"({contest.get('title', 'Unknown')}) with {participant_count} participants")
                    
                except Exception as e:
                    results["errors"].append({
                        "contest_id": contest_id,
                        "error": str(e)
                    })
                    print(f"[ERROR] Failed to auto-start contest {contest_id}: {str(e)}")
            
        except Exception as e:
            print(f"[ERROR] auto_start_contests job failed: {str(e)}")
            results["errors"].append({"error": str(e)})
        
        return results
    
    async def auto_complete_contests(self) -> Dict[str, Any]:
        """
        Auto-complete contests when end_date + grace period is reached.
        
        Two scenarios:
        1. Has approved submissions -> Complete and distribute prizes
        2. No approved submissions -> Complete and refund owner
        
        Conditions:
        - status = ACTIVE or JUDGING
        - end_date + grace_period <= now
        """
        now = datetime.utcnow()
        results = {
            "processed": 0,
            "completed": [],
            "refunded": [],
            "errors": []
        }
        
        try:
            # Find contests past their end date + grace period
            # Default grace period is 24 hours
            contests_to_process = await self.contests.find({
                "status": {"$in": [ContestStatus.ACTIVE, ContestStatus.JUDGING]},
                "is_active": True,
                "end_date": {"$lte": now}
            }).to_list(length=100)
            
            for contest in contests_to_process:
                contest_id = str(contest["_id"])
                grace_hours = contest.get("grace_period_hours", 24)
                grace_deadline = contest["end_date"] + timedelta(hours=grace_hours)
                
                # Skip if still in grace period
                if now < grace_deadline:
                    continue
                
                try:
                    # Check submission status
                    submission_count = await self.submissions.count_documents({
                        "contest_id": contest_id
                    })
                    
                    approved_count = await self.submissions.count_documents({
                        "contest_id": contest_id,
                        "status": "approved"
                    })
                    
                    participant_count = await self.participants.count_documents({
                        "contest_id": contest_id
                    })
                    
                    if approved_count > 0:
                        # Has approved submissions -> Complete with prize distribution
                        await self._complete_with_distribution(
                            contest, participant_count, submission_count, approved_count, now
                        )
                        results["completed"].append({
                            "contest_id": contest_id,
                            "title": contest.get("title", "Unknown"),
                            "participants": participant_count,
                            "approved_submissions": approved_count
                        })
                    else:
                        # No approved submissions -> Refund owner
                        await self._complete_with_refund(
                            contest, participant_count, submission_count, now
                        )
                        results["refunded"].append({
                            "contest_id": contest_id,
                            "title": contest.get("title", "Unknown"),
                            "participants": participant_count,
                            "submissions": submission_count,
                            "reason": "no_approved_submissions"
                        })
                    
                    results["processed"] += 1
                    
                except Exception as e:
                    results["errors"].append({
                        "contest_id": contest_id,
                        "error": str(e)
                    })
                    print(f"[ERROR] Failed to auto-complete contest {contest_id}: {str(e)}")
            
        except Exception as e:
            print(f"[ERROR] auto_complete_contests job failed: {str(e)}")
            results["errors"].append({"error": str(e)})
        
        return results
    
    async def _complete_with_distribution(
        self,
        contest: dict,
        participant_count: int,
        submission_count: int,
        approved_count: int,
        now: datetime
    ):
        """
        Complete contest and distribute prizes.
        """
        from app.services.contest.prize_distribution import PrizeDistributionService
        
        contest_id = str(contest["_id"])
        owner_id = contest["owner_id"]
        
        # Distribute prizes
        prize_service = PrizeDistributionService(self.db)
        success, message, details = await prize_service.distribute_prizes(
            contest_id=contest_id,
            owner_id=owner_id,
            distribution_mode="proportional"
        )
        
        # Update contest status
        await self.contests.update_one(
            {"_id": contest["_id"]},
            {"$set": {
                "status": ContestStatus.COMPLETED,
                "is_active": True,  # Keep visible for archive
                "completed_at": now,
                "auto_completed": True,
                "updated_at": now
            }}
        )
        
        # Log to audit trail
        await self.audit_service.log_action(
            contest_id=contest_id,
            action=AuditAction.CONTEST_COMPLETED,
            user_id="system",
            username="System Scheduler",
            entity_type="contest",
            entity_id=contest_id,
            metadata={
                "trigger": "auto_complete",
                "participant_count": participant_count,
                "submission_count": submission_count,
                "approved_count": approved_count,
                "prize_distributed": success,
                "distribution_message": message
            }
        )
        
        print(f"[SCHEDULER] Auto-completed contest: {contest_id} "
              f"({contest.get('title', 'Unknown')}) - Prizes distributed: {success}")
    
    async def _complete_with_refund(
        self,
        contest: dict,
        participant_count: int,
        submission_count: int,
        now: datetime
    ):
        """
        Complete contest and refund owner (no approved submissions).
        """
        from app.services.contest.prize_distribution import PrizeDistributionService
        
        contest_id = str(contest["_id"])
        
        # Process refund
        prize_service = PrizeDistributionService(self.db)
        success, message, details = await prize_service.process_no_submission_refund(
            contest_id=contest_id
        )
        
        # Update contest status
        await self.contests.update_one(
            {"_id": contest["_id"]},
            {"$set": {
                "status": ContestStatus.COMPLETED,
                "is_active": True,  # Keep visible for archive
                "completed_at": now,
                "auto_completed": True,
                "refund_processed": success,
                "updated_at": now
            }}
        )
        
        # Log to audit trail
        await self.audit_service.log_action(
            contest_id=contest_id,
            action=AuditAction.CONTEST_COMPLETED,
            user_id="system",
            username="System Scheduler",
            entity_type="contest",
            entity_id=contest_id,
            metadata={
                "trigger": "auto_complete_refund",
                "participant_count": participant_count,
                "submission_count": submission_count,
                "approved_count": 0,
                "refund_processed": success,
                "refund_message": message,
                "reason": "no_approved_submissions"
            }
        )
        
        print(f"[SCHEDULER] Auto-completed contest with refund: {contest_id} "
              f"({contest.get('title', 'Unknown')}) - Refund: {success}")
    
    async def transition_to_judging(self) -> Dict[str, Any]:
        """
        Transition ACTIVE contests to JUDGING when end_date is reached.
        
        This gives owners time to review submissions before auto-complete.
        """
        now = datetime.utcnow()
        results = {
            "processed": 0,
            "transitioned": [],
            "errors": []
        }
        
        try:
            # Find active contests past end_date
            contests = await self.contests.find({
                "status": ContestStatus.ACTIVE,
                "is_active": True,
                "end_date": {"$lte": now}
            }).to_list(length=100)
            
            for contest in contests:
                contest_id = str(contest["_id"])
                
                try:
                    await self.contests.update_one(
                        {"_id": contest["_id"]},
                        {"$set": {
                            "status": ContestStatus.JUDGING,
                            "updated_at": now
                        }}
                    )
                    
                    # Log to audit
                    await self.audit_service.log_action(
                        contest_id=contest_id,
                        action=AuditAction.CONTEST_UPDATED,
                        user_id="system",
                        username="System Scheduler",
                        entity_type="contest",
                        entity_id=contest_id,
                        changes={"status": {"from": "active", "to": "judging"}},
                        metadata={"trigger": "end_date_reached"}
                    )
                    
                    results["transitioned"].append({
                        "contest_id": contest_id,
                        "title": contest.get("title", "Unknown")
                    })
                    results["processed"] += 1
                    
                    print(f"[SCHEDULER] Contest transitioned to JUDGING: {contest_id}")
                    
                except Exception as e:
                    results["errors"].append({
                        "contest_id": contest_id,
                        "error": str(e)
                    })
            
        except Exception as e:
            print(f"[ERROR] transition_to_judging job failed: {str(e)}")
        
        return results
    
    async def retry_failed_prize_credits(self) -> Dict[str, Any]:
        """
        Retry crediting prizes that failed during initial distribution.
        
        This ensures no winner loses their prize due to temporary failures.
        """
        from app.services.contest.prize_distribution import PrizeDistributionService
        from app.utils.wallet import WalletUtils
        from app.models.payment.transaction import TransactionCategory
        
        results = {
            "processed": 0,
            "retried": [],
            "errors": []
        }
        
        try:
            # Find contests with failed credits
            contests_with_failures = await self.contests.find({
                "prizes_distributed": True,
                "failed_credits": {"$exists": True, "$ne": None, "$not": {"$size": 0}}
            }).to_list(length=50)
            
            wallet_utils = WalletUtils(self.db)
            
            for contest in contests_with_failures:
                contest_id = str(contest["_id"])
                contest_title = contest.get("title", "Unknown")
                failed_credits = contest.get("failed_credits", [])
                
                successfully_retried = []
                still_failed = []
                
                for failed in failed_credits:
                    user_id = failed["user_id"]
                    amount = failed["amount"]
                    
                    # Retry credit (idempotency key ensures no double payment)
                    credit_success, credit_message, txn = await wallet_utils.add_balance(
                        user_id=user_id,
                        amount=amount,
                        category=TransactionCategory.CONTEST_PRIZE,
                        description=f"Contest prize (retry) - {contest_title}",
                        reference_type="contest_prize",
                        reference_id=contest_id,
                        idempotency_key=f"PRIZE_{contest_id}_{user_id}"
                    )
                    
                    if credit_success:
                        successfully_retried.append(user_id)
                        # Update participant record
                        await self.participants.update_one(
                            {"contest_id": contest_id, "user_id": user_id},
                            {"$set": {
                                "prize_distributed": True,
                                "prize_distributed_at": datetime.utcnow(),
                                "credit_failed": False,
                                "credit_error": None
                            }}
                        )
                        print(f"[SCHEDULER] Successfully retried prize credit for user {user_id} in contest {contest_id}")
                    else:
                        still_failed.append(failed)
                
                # Update contest with remaining failures
                if still_failed:
                    await self.contests.update_one(
                        {"_id": contest["_id"]},
                        {"$set": {"failed_credits": still_failed}}
                    )
                else:
                    # All retries successful - clear failed_credits
                    await self.contests.update_one(
                        {"_id": contest["_id"]},
                        {"$unset": {"failed_credits": ""}}
                    )
                
                if successfully_retried:
                    results["retried"].append({
                        "contest_id": contest_id,
                        "users": successfully_retried
                    })
                    results["processed"] += len(successfully_retried)
            
        except Exception as e:
            print(f"[ERROR] retry_failed_prize_credits job failed: {str(e)}")
            results["errors"].append({"error": str(e)})
        
        return results
    
    async def run_all_jobs(self) -> Dict[str, Any]:
        """
        Run all scheduler jobs (for manual trigger or testing).
        """
        results = {
            "auto_start": await self.auto_start_contests(),
            "to_judging": await self.transition_to_judging(),
            "auto_complete": await self.auto_complete_contests(),
            "retry_failed_credits": await self.retry_failed_prize_credits(),
            "run_at": datetime.utcnow().isoformat()
        }
        return results
