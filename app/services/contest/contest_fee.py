"""
Contest Fee Service - Fully Dynamic
All settings loaded from database - no hardcoded values
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.models.contest.contest_config import (
    ContestFeeConfig, ContestFeeCalculation, ContestCreationValidation
)
from app.models.payment.transaction import TransactionCategory, TransactionType
from app.utils.wallet import WalletUtils


class ContestFeeService:
    """
    Fully Dynamic Contest Fee Service.
    
    All configuration from database:
    - Global settings from contest_config collection
    
    Security Features:
    - Balance validation before creation
    - Credit locking for prize pool
    - Platform fee deduction
    - Refund on cancellation
    """
    
    # Default config (used only if DB has no config - fallback)
    DEFAULT_CONFIG = {
        "config_id": "global",
        "creation_fee_type": "percentage",
        "creation_fee_percentage": 5.0,
        "creation_fee_fixed": 0.0,
        "creation_fee_min": 10.0,
        "creation_fee_max": 1000.0,
        "min_prize_pool": 100.0,
        "max_prize_pool": 1000000.0,
        "max_active_contests_per_user": 5,
        "max_participants_limit": 10000,
        "min_participants": 2,
        "entry_fee_enabled": True,
        "entry_fee_max_percentage": 50.0,
        "entry_fee_platform_cut": 10.0,
        "refund_on_cancel": True,
        "refund_percentage": 95.0,
        "min_time_before_cancel": 24,
        "auto_distribute_prizes": False,
        "prize_hold_days": 7,
        "contest_creation_enabled": True,
        "require_kyc_for_creation": False,
        "require_email_verified": True,
        "min_account_age_days": 0,
        "maintenance_mode": False,
        "maintenance_message": ""
    }
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.config_collection = db.contest_config
        self.contests = db.contests
        self.wallet_utils = WalletUtils(db)
        self._cached_config: Optional[Dict] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes
    
    async def _get_config(self) -> Dict[str, Any]:
        """
        Get global contest configuration from database.
        Uses caching to reduce DB calls.
        """
        now = datetime.utcnow()
        
        # Check cache
        if (self._cached_config and self._cache_time and 
            (now - self._cache_time) < self._cache_ttl):
            return self._cached_config
        
        # Load from DB
        config = await self.config_collection.find_one({"config_id": "global"})
        
        if not config:
            # Create default config if not exists
            config = {**self.DEFAULT_CONFIG, "created_at": now, "updated_at": now}
            await self.config_collection.insert_one(config)
        
        # Remove MongoDB _id for cleaner handling
        if "_id" in config:
            config["_id"] = str(config["_id"])
        
        self._cached_config = config
        self._cache_time = now
        
        return config
    
    def clear_cache(self):
        """Clear configuration cache (call after admin updates)"""
        self._cached_config = None
        self._cache_time = None
    
    async def calculate_creation_fee(self, prize_pool: float) -> ContestFeeCalculation:
        """
        Calculate contest creation fees dynamically from database config.
        
        Fee calculation based on config:
        - fixed: Just fixed fee
        - percentage: prize_pool * percentage
        - mixed: fixed + (prize_pool * percentage)
        
        Then apply min/max caps.
        """
        config = await self._get_config()
        
        fee_type = config.get("creation_fee_type", "percentage")
        fee_percentage = config.get("creation_fee_percentage", 5.0)
        fee_fixed = config.get("creation_fee_fixed", 0.0)
        fee_min = config.get("creation_fee_min", 10.0)
        fee_max = config.get("creation_fee_max", 1000.0)
        
        # Calculate fee based on type
        if fee_type == "fixed":
            platform_fee = fee_fixed
        elif fee_type == "percentage":
            platform_fee = prize_pool * (fee_percentage / 100)
        elif fee_type == "mixed":
            platform_fee = fee_fixed + (prize_pool * (fee_percentage / 100))
        else:
            platform_fee = prize_pool * (fee_percentage / 100)
        
        # Apply min/max caps
        if fee_min > 0:
            platform_fee = max(platform_fee, fee_min)
        if fee_max > 0:
            platform_fee = min(platform_fee, fee_max)
        
        platform_fee = round(platform_fee, 2)
        total_required = round(prize_pool + platform_fee, 2)
        
        return ContestFeeCalculation(
            prize_pool=prize_pool,
            platform_fee_percentage=fee_percentage,
            platform_fee_fixed=fee_fixed,
            platform_fee_total=platform_fee,
            total_required=total_required,
            currency="credits"
        )
    
    async def validate_contest_creation(
        self,
        user_id: str,
        prize_pool: float,
        max_participants: int
    ) -> ContestCreationValidation:
        """
        Validate if user can create a contest.
        
        Checks:
        1. Contest creation is enabled
        2. Not in maintenance mode
        3. Prize pool within limits
        4. Participants within limits
        5. User has enough balance
        6. User hasn't exceeded active contest limit
        """
        config = await self._get_config()
        
        # Check if creation is enabled
        if not config.get("contest_creation_enabled", True):
            return ContestCreationValidation(
                can_create=False,
                reason="Contest creation is currently disabled"
            )
        
        # Check maintenance mode
        if config.get("maintenance_mode", False):
            msg = config.get("maintenance_message", "Contest creation is under maintenance")
            return ContestCreationValidation(
                can_create=False,
                reason=msg
            )
        
        # Validate prize pool
        min_prize = config.get("min_prize_pool", 100)
        max_prize = config.get("max_prize_pool", 1000000)
        
        if prize_pool < min_prize:
            return ContestCreationValidation(
                can_create=False,
                reason=f"Minimum prize pool is {min_prize} credits"
            )
        
        if prize_pool > max_prize:
            return ContestCreationValidation(
                can_create=False,
                reason=f"Maximum prize pool is {max_prize} credits"
            )
        
        # Validate participants
        min_participants = config.get("min_participants", 2)
        max_participants_limit = config.get("max_participants_limit", 10000)
        
        if max_participants < min_participants:
            return ContestCreationValidation(
                can_create=False,
                reason=f"Minimum participants required is {min_participants}"
            )
        
        if max_participants > max_participants_limit:
            return ContestCreationValidation(
                can_create=False,
                reason=f"Maximum participants allowed is {max_participants_limit}"
            )
        
        # Check active contests limit
        max_active = config.get("max_active_contests_per_user", 5)
        active_count = await self.contests.count_documents({
            "owner_id": user_id,
            "status": {"$in": ["draft", "active", "upcoming"]}
        })
        
        if active_count >= max_active:
            return ContestCreationValidation(
                can_create=False,
                reason=f"You have reached the maximum of {max_active} active contests",
                active_contests=active_count
            )
        
        # Calculate fees
        fee_calc = await self.calculate_creation_fee(prize_pool)
        
        # Check user balance
        available_balance, locked_balance = await self.wallet_utils.get_balance(user_id)
        
        if available_balance < fee_calc.total_required:
            return ContestCreationValidation(
                can_create=False,
                reason=f"Insufficient balance. Required: {fee_calc.total_required} credits (Prize: {prize_pool} + Fee: {fee_calc.platform_fee_total}). Available: {available_balance}",
                fee_breakdown=fee_calc,
                user_balance=available_balance,
                active_contests=active_count
            )
        
        # All validations passed
        return ContestCreationValidation(
            can_create=True,
            fee_breakdown=fee_calc,
            user_balance=available_balance,
            active_contests=active_count
        )
    
    async def process_contest_creation_payment(
        self,
        user_id: str,
        contest_id: str,
        contest_title: str,
        prize_pool: float
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Process payment for contest creation.
        
        Flow:
        1. Calculate fees
        2. Lock prize pool credits
        3. Deduct platform fee
        4. Return transaction details
        """
        try:
            # Calculate fees
            fee_calc = await self.calculate_creation_fee(prize_pool)
            
            # Check balance again (security - prevent race conditions)
            available_balance, _ = await self.wallet_utils.get_balance(user_id)
            if available_balance < fee_calc.total_required:
                return False, f"Insufficient balance. Required: {fee_calc.total_required}", None
            
            transactions = {}
            
            # 1. Lock prize pool credits
            lock_success, lock_message = await self.wallet_utils.lock_balance(
                user_id=user_id,
                amount=prize_pool,
                reason=f"Prize pool for contest: {contest_title}",
                reference_type="contest_prize",
                reference_id=contest_id
            )
            
            if not lock_success:
                return False, f"Failed to lock prize pool: {lock_message}", None
            
            transactions["prize_pool_locked"] = prize_pool
            
            # 2. Deduct platform fee (this is actually spent, not locked)
            if fee_calc.platform_fee_total > 0:
                fee_success, fee_message, fee_txn = await self.wallet_utils.deduct_balance(
                    user_id=user_id,
                    amount=fee_calc.platform_fee_total,
                    category=TransactionCategory.CONTEST_CREATE,
                    description=f"Contest creation fee for: {contest_title}",
                    reference_type="contest_creation_fee",
                    reference_id=contest_id,
                    idempotency_key=f"CONTEST_FEE_{contest_id}"
                )
                
                if not fee_success:
                    # Unlock prize pool if fee deduction fails
                    await self.wallet_utils.unlock_balance(
                        user_id=user_id,
                        amount=prize_pool,
                        reason=f"Reverting prize pool lock due to fee failure",
                        reference_type="contest_prize",
                        reference_id=contest_id
                    )
                    return False, f"Failed to deduct platform fee: {fee_message}", None
                
                transactions["platform_fee_deducted"] = fee_calc.platform_fee_total
                transactions["platform_fee_transaction_id"] = fee_txn.get("transaction_id") if fee_txn else None
            
            print(f"[OK] Contest creation payment processed for {contest_id}: "
                  f"Prize locked={prize_pool}, Fee={fee_calc.platform_fee_total}")
            
            return True, "Payment processed successfully", {
                "prize_pool": prize_pool,
                "platform_fee": fee_calc.platform_fee_total,
                "total_charged": fee_calc.total_required,
                "transactions": transactions
            }
            
        except Exception as e:
            print(f"[ERROR] process_contest_creation_payment failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Payment processing failed: {str(e)}", None
    
    async def process_contest_cancellation_refund(
        self,
        user_id: str,
        contest_id: str,
        contest_title: str,
        prize_pool: float
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Process refund for contest cancellation.
        
        Flow:
        1. Unlock prize pool
        2. Optionally deduct cancellation fee
        3. Return refund details
        """
        try:
            config = await self._get_config()
            
            if not config.get("refund_on_cancel", True):
                return False, "Refunds are disabled for contest cancellation", None
            
            refund_percentage = config.get("refund_percentage", 95.0)
            
            # Unlock prize pool
            unlock_success, unlock_message = await self.wallet_utils.unlock_balance(
                user_id=user_id,
                amount=prize_pool,
                reason=f"Contest cancelled: {contest_title}",
                reference_type="contest_prize",
                reference_id=contest_id
            )
            
            if not unlock_success:
                print(f"[WARN] Failed to unlock prize pool for contest {contest_id}: {unlock_message}")
            
            # Calculate cancellation fee (if any)
            cancellation_fee = 0.0
            if refund_percentage < 100:
                cancellation_fee = prize_pool * ((100 - refund_percentage) / 100)
                
                # Deduct cancellation fee
                if cancellation_fee > 0:
                    await self.wallet_utils.deduct_balance(
                        user_id=user_id,
                        amount=cancellation_fee,
                        category=TransactionCategory.CONTEST_ENTRY,
                        description=f"Cancellation fee for contest: {contest_title}",
                        reference_type="contest_cancellation_fee",
                        reference_id=contest_id,
                        idempotency_key=f"CONTEST_CANCEL_FEE_{contest_id}"
                    )
            
            net_refund = prize_pool - cancellation_fee
            
            print(f"[OK] Contest cancellation refund processed for {contest_id}: "
                  f"Prize unlocked={prize_pool}, CancelFee={cancellation_fee}, Net={net_refund}")
            
            return True, "Refund processed successfully", {
                "prize_pool_unlocked": prize_pool,
                "cancellation_fee": cancellation_fee,
                "net_refund": net_refund
            }
            
        except Exception as e:
            print(f"[ERROR] process_contest_cancellation_refund failed: {str(e)}")
            return False, f"Refund processing failed: {str(e)}", None
    
    async def release_prize_pool(
        self,
        contest_id: str,
        owner_id: str,
        prize_pool: float,
        winners: List[Dict[str, Any]]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Release prize pool to winners.
        
        Winners format: [{"user_id": str, "amount": float, "rank": int}, ...]
        """
        try:
            # Unlock from owner's wallet
            unlock_success, unlock_message = await self.wallet_utils.unlock_balance(
                user_id=owner_id,
                amount=prize_pool,
                reason=f"Prize pool released for contest {contest_id}",
                reference_type="contest_prize",
                reference_id=contest_id
            )
            
            if not unlock_success:
                print(f"[WARN] Failed to unlock prize pool: {unlock_message}")
            
            # Deduct from owner and credit to winners
            deduct_success, deduct_message, _ = await self.wallet_utils.deduct_balance(
                user_id=owner_id,
                amount=prize_pool,
                category=TransactionCategory.CONTEST_ENTRY,
                description=f"Prize pool payout for contest {contest_id}",
                reference_type="contest_prize_payout",
                reference_id=contest_id,
                idempotency_key=f"PRIZE_PAYOUT_{contest_id}"
            )
            
            if not deduct_success:
                return False, f"Failed to deduct prize pool: {deduct_message}", None
            
            # Credit each winner
            payouts = []
            for winner in winners:
                credit_success, credit_message, txn = await self.wallet_utils.add_balance(
                    user_id=winner["user_id"],
                    amount=winner["amount"],
                    category=TransactionCategory.CONTEST_PRIZE,
                    description=f"Contest prize (Rank #{winner['rank']})",
                    reference_type="contest_prize",
                    reference_id=contest_id,
                    idempotency_key=f"PRIZE_{contest_id}_{winner['user_id']}"
                )
                
                payouts.append({
                    "user_id": winner["user_id"],
                    "amount": winner["amount"],
                    "rank": winner["rank"],
                    "success": credit_success,
                    "transaction_id": txn.get("transaction_id") if txn else None
                })
            
            return True, "Prize pool distributed", {"payouts": payouts}
            
        except Exception as e:
            print(f"[ERROR] release_prize_pool failed: {str(e)}")
            return False, f"Prize distribution failed: {str(e)}", None
    
    async def get_config(self) -> Dict[str, Any]:
        """Get full contest configuration (public info)"""
        config = await self._get_config()
        
        return {
            "creation_fee_type": config.get("creation_fee_type", "percentage"),
            "creation_fee_percentage": config.get("creation_fee_percentage", 5.0),
            "creation_fee_fixed": config.get("creation_fee_fixed", 0.0),
            "creation_fee_min": config.get("creation_fee_min", 10.0),
            "creation_fee_max": config.get("creation_fee_max", 1000.0),
            "min_prize_pool": config.get("min_prize_pool", 100.0),
            "max_prize_pool": config.get("max_prize_pool", 1000000.0),
            "max_active_contests_per_user": config.get("max_active_contests_per_user", 5),
            "max_participants_limit": config.get("max_participants_limit", 10000),
            "min_participants": config.get("min_participants", 2),
            "entry_fee_enabled": config.get("entry_fee_enabled", True),
            "entry_fee_max_percentage": config.get("entry_fee_max_percentage", 50.0),
            "refund_on_cancel": config.get("refund_on_cancel", True),
            "refund_percentage": config.get("refund_percentage", 95.0),
            "contest_creation_enabled": config.get("contest_creation_enabled", True),
            "maintenance_mode": config.get("maintenance_mode", False),
            "maintenance_message": config.get("maintenance_message", "")
        }
    
    async def update_config(self, updates: Dict[str, Any], admin_id: str) -> Tuple[bool, str]:
        """Admin: Update global contest configuration"""
        try:
            updates["updated_at"] = datetime.utcnow()
            updates["updated_by"] = admin_id
            
            await self.config_collection.update_one(
                {"config_id": "global"},
                {"$set": updates},
                upsert=True
            )
            
            self.clear_cache()
            return True, "Configuration updated"
        except Exception as e:
            return False, f"Failed to update config: {str(e)}"
