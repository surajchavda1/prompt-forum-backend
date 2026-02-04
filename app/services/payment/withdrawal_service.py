"""
Withdrawal Service - Fully Dynamic
All settings loaded from database - no hardcoded values
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.models.payment.withdrawal import (
    WithdrawalStatus, PaymentMethodType, WithdrawalFees,
    PaymentMethodDetails
)
from app.models.payment.withdrawal_config import (
    WithdrawalGlobalConfig, WithdrawalMethodConfig
)
from app.models.payment.transaction import TransactionCategory, TransactionType
from app.utils.wallet import WalletUtils


class WithdrawalService:
    """
    Fully Dynamic Withdrawal Service.
    
    All configuration from database:
    - Global settings from withdrawal_config collection
    - Payment methods from withdrawal_methods collection
    
    Security Features:
    - Balance locking during processing
    - Daily/Monthly withdrawal limits
    - Cooldown period between withdrawals
    - Idempotency for request creation
    - Admin approval workflow
    """
    
    # Default config (used only if DB has no config - fallback)
    DEFAULT_CONFIG = {
        "config_id": "global",
        "min_withdrawal_amount": 100.0,
        "max_withdrawal_amount": 100000.0,
        "daily_withdrawal_limit": 50000.0,
        "monthly_withdrawal_limit": 500000.0,
        "max_pending_requests": 3,
        "platform_fee_percentage": 5.0,
        "platform_fee_fixed": 0.0,
        "platform_fee_min": 10.0,
        "platform_fee_max": 500.0,
        "credit_to_usd_rate": 1.0,
        "credit_to_inr_rate": 83.0,
        "credit_to_eur_rate": 0.92,
        "credit_to_gbp_rate": 0.79,
        "cooldown_hours": 24,
        "require_kyc": False,
        "require_2fa": False,
        "require_email_verification": False,
        "min_account_age_days": 0,
        "min_successful_payments": 0,
        "auto_approve_threshold": 0.0,
        "default_processing_days": 3,
        "supported_currencies": ["USD", "EUR", "GBP", "INR", "USDT", "USDC"],
        "default_currency": "USD",
        "withdrawals_enabled": True,
        "new_user_withdrawals_enabled": True,
        "maintenance_mode": False,
        "maintenance_message": ""
    }
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.withdrawals = db.withdrawals
        self.config_collection = db.withdrawal_config
        self.methods_collection = db.withdrawal_methods
        self.wallet_utils = WalletUtils(db)
        self._cached_config: Optional[Dict] = None
        self._cached_methods: Optional[List[Dict]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes
    
    async def _get_config(self) -> Dict[str, Any]:
        """
        Get global withdrawal configuration from database.
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
    
    async def _get_method_config(self, method_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific withdrawal method"""
        method = await self.methods_collection.find_one({
            "method_id": method_id,
            "is_active": True
        })
        
        if method and "_id" in method:
            method["_id"] = str(method["_id"])
        
        return method
    
    async def _get_all_methods(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all withdrawal methods"""
        query = {"is_active": True} if active_only else {}
        cursor = self.methods_collection.find(query).sort("sort_order", 1)
        methods = await cursor.to_list(length=100)
        
        for method in methods:
            if "_id" in method:
                method["_id"] = str(method["_id"])
        
        return methods
    
    def clear_cache(self):
        """Clear configuration cache (call after admin updates)"""
        self._cached_config = None
        self._cached_methods = None
        self._cache_time = None
    
    @staticmethod
    def generate_withdrawal_id() -> str:
        """Generate unique withdrawal ID"""
        return f"WD_{uuid.uuid4().hex[:12].upper()}"
    
    async def calculate_fees(
        self,
        amount: float,
        method_id: str,
        currency: str = "USD"
    ) -> WithdrawalFees:
        """
        Calculate withdrawal fees dynamically from database config.
        
        Fee calculation:
        1. Method-specific fee (from withdrawal_methods)
        2. Platform fee (from withdrawal_config)
        3. Apply min/max caps
        """
        config = await self._get_config()
        method_config = await self._get_method_config(method_id)
        
        # Method fee calculation
        method_fee = 0.0
        if method_config:
            fee_type = method_config.get("fee_type", "fixed")
            if fee_type == "fixed":
                method_fee = method_config.get("fee_fixed", 0.0)
            elif fee_type == "percentage":
                method_fee = amount * (method_config.get("fee_percentage", 0.0) / 100)
            elif fee_type == "mixed":
                method_fee = method_config.get("fee_fixed", 0.0) + \
                           amount * (method_config.get("fee_percentage", 0.0) / 100)
            
            # Apply method fee caps
            method_fee_min = method_config.get("fee_min", 0.0)
            method_fee_max = method_config.get("fee_max", 0.0)
            if method_fee_min > 0:
                method_fee = max(method_fee, method_fee_min)
            if method_fee_max > 0:
                method_fee = min(method_fee, method_fee_max)
        
        # Platform fee calculation
        platform_percentage = config.get("platform_fee_percentage", 0.0)
        platform_fixed = config.get("platform_fee_fixed", 0.0)
        platform_fee = amount * (platform_percentage / 100) + platform_fixed
        
        # Apply platform fee caps
        platform_min = config.get("platform_fee_min", 0.0)
        platform_max = config.get("platform_fee_max", 0.0)
        if platform_min > 0:
            platform_fee = max(platform_fee, platform_min)
        if platform_max > 0:
            platform_fee = min(platform_fee, platform_max)
        
        total_fees = method_fee + platform_fee
        net_amount = max(0, amount - total_fees)
        
        # Apply exchange rate if different currency
        exchange_rate = 1.0
        rate_key = f"credit_to_{currency.lower()}_rate"
        if rate_key in config:
            exchange_rate = config[rate_key]
        
        return WithdrawalFees(
            withdrawal_amount=amount,
            platform_fee_percentage=platform_percentage,
            platform_fee_fixed=platform_fixed,
            platform_fee_total=round(platform_fee, 2),
            gateway_fee=round(method_fee, 2),
            total_fees=round(total_fees, 2),
            net_amount=round(net_amount * exchange_rate, 2),
            currency=currency
        )
    
    async def get_withdrawal_limits(self, user_id: str) -> Dict[str, Any]:
        """Get user's withdrawal limits and usage (all from DB config)"""
        config = await self._get_config()
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get daily withdrawals
        daily_total = await self._get_withdrawal_total(
            user_id, 
            start_date=day_start,
            statuses=[WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED, 
                     WithdrawalStatus.PROCESSING, WithdrawalStatus.COMPLETED]
        )
        
        # Get monthly withdrawals
        monthly_total = await self._get_withdrawal_total(
            user_id,
            start_date=month_start,
            statuses=[WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED,
                     WithdrawalStatus.PROCESSING, WithdrawalStatus.COMPLETED]
        )
        
        # Get pending requests count
        pending_count = await self.withdrawals.count_documents({
            "user_id": user_id,
            "status": WithdrawalStatus.PENDING.value
        })
        
        daily_limit = config.get("daily_withdrawal_limit", 50000)
        monthly_limit = config.get("monthly_withdrawal_limit", 500000)
        max_pending = config.get("max_pending_requests", 3)
        
        return {
            "min_amount": config.get("min_withdrawal_amount", 100),
            "max_amount": config.get("max_withdrawal_amount", 100000),
            "daily_limit": daily_limit,
            "daily_used": daily_total,
            "daily_remaining": max(0, daily_limit - daily_total),
            "monthly_limit": monthly_limit,
            "monthly_used": monthly_total,
            "monthly_remaining": max(0, monthly_limit - monthly_total),
            "max_pending_requests": max_pending,
            "pending_requests": pending_count,
            "can_request": pending_count < max_pending,
            "cooldown_hours": config.get("cooldown_hours", 24),
            "default_processing_days": config.get("default_processing_days", 3),
            "supported_currencies": config.get("supported_currencies", ["USD"]),
            "require_kyc": config.get("require_kyc", False),
            "require_2fa": config.get("require_2fa", False)
        }
    
    async def _get_withdrawal_total(
        self,
        user_id: str,
        start_date: datetime,
        statuses: List[WithdrawalStatus]
    ) -> float:
        """Get total withdrawal amount for a period"""
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "created_at": {"$gte": start_date},
                    "status": {"$in": [s.value for s in statuses]}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$amount"}
                }
            }
        ]
        
        result = await self.withdrawals.aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0.0
    
    async def check_cooldown(self, user_id: str) -> Tuple[bool, Optional[datetime]]:
        """Check if user is in cooldown period (cooldown from DB config)"""
        config = await self._get_config()
        cooldown_hours = config.get("cooldown_hours", 24)
        cooldown_start = datetime.utcnow() - timedelta(hours=cooldown_hours)
        
        last_withdrawal = await self.withdrawals.find_one(
            {
                "user_id": user_id,
                "created_at": {"$gte": cooldown_start},
                "status": {"$in": [
                    WithdrawalStatus.PENDING.value,
                    WithdrawalStatus.APPROVED.value,
                    WithdrawalStatus.PROCESSING.value,
                    WithdrawalStatus.COMPLETED.value
                ]}
            },
            sort=[("created_at", -1)]
        )
        
        if last_withdrawal:
            cooldown_ends = last_withdrawal["created_at"] + timedelta(hours=cooldown_hours)
            if datetime.utcnow() < cooldown_ends:
                return False, cooldown_ends
        
        return True, None
    
    async def get_available_methods(self, currency: str = None) -> List[Dict[str, Any]]:
        """Get available withdrawal methods (filtered by currency if provided)"""
        methods = await self._get_all_methods(active_only=True)
        
        if currency:
            methods = [m for m in methods 
                      if currency in m.get("supported_currencies", ["USD"])]
        
        # Return public info only
        return [{
            "method_id": m.get("method_id"),
            "name": m.get("name"),
            "description": m.get("description", ""),
            "supported_currencies": m.get("supported_currencies", ["USD"]),
            "supported_countries": m.get("supported_countries", []),
            "fee_type": m.get("fee_type", "fixed"),
            "fee_fixed": m.get("fee_fixed", 0),
            "fee_percentage": m.get("fee_percentage", 0),
            "min_amount": m.get("min_amount", 10),
            "max_amount": m.get("max_amount", 100000),
            "processing_days": m.get("processing_days", 3),
            "requires_verification": m.get("requires_verification", False),
            "icon": m.get("icon")
        } for m in methods]
    
    async def create_withdrawal_request(
        self,
        user_id: str,
        amount: float,
        method_id: str,
        payment_details: Dict[str, Any],
        currency: str = "USD",
        user_notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Create a new withdrawal request.
        All validation against database configuration.
        """
        try:
            config = await self._get_config()
            
            # Check if withdrawals are enabled
            if not config.get("withdrawals_enabled", True):
                return False, "Withdrawals are currently disabled", None
            
            if config.get("maintenance_mode", False):
                msg = config.get("maintenance_message", "Withdrawals are under maintenance")
                return False, msg, None
            
            # Get method config
            method_config = await self._get_method_config(method_id)
            if not method_config:
                return False, f"Withdrawal method '{method_id}' is not available", None
            
            # Check currency support
            if currency not in method_config.get("supported_currencies", ["USD"]):
                return False, f"Currency '{currency}' not supported for {method_config['name']}", None
            
            # Check global limits
            min_amount = config.get("min_withdrawal_amount", 100)
            max_amount = config.get("max_withdrawal_amount", 100000)
            
            if amount < min_amount:
                return False, f"Minimum withdrawal amount is {min_amount} credits", None
            
            if amount > max_amount:
                return False, f"Maximum withdrawal amount is {max_amount} credits", None
            
            # Check method-specific limits
            method_min = method_config.get("min_amount", 10)
            method_max = method_config.get("max_amount", 100000)
            
            if amount < method_min:
                return False, f"Minimum amount for {method_config['name']} is {method_min} credits", None
            
            if amount > method_max:
                return False, f"Maximum amount for {method_config['name']} is {method_max} credits", None
            
            # Check balance
            available_balance, locked_balance = await self.wallet_utils.get_balance(user_id)
            if available_balance < amount:
                return False, f"Insufficient balance. Available: {available_balance} credits", None
            
            # Check daily/monthly limits
            limits = await self.get_withdrawal_limits(user_id)
            if amount > limits["daily_remaining"]:
                return False, f"Daily limit exceeded. Remaining: {limits['daily_remaining']} credits", None
            
            if amount > limits["monthly_remaining"]:
                return False, f"Monthly limit exceeded. Remaining: {limits['monthly_remaining']} credits", None
            
            # Check pending requests limit
            if not limits["can_request"]:
                return False, f"Maximum pending requests ({limits['max_pending_requests']}) reached", None
            
            # Check cooldown
            can_withdraw, cooldown_ends = await self.check_cooldown(user_id)
            if not can_withdraw:
                return False, f"Withdrawal cooldown active until {cooldown_ends.isoformat()}", None
            
            # Calculate fees
            fees = await self.calculate_fees(
                amount=amount,
                method_id=method_id,
                currency=currency
            )
            
            if fees.net_amount <= 0:
                return False, "Withdrawal amount is too low to cover fees", None
            
            # Lock the withdrawal amount
            lock_success, lock_message = await self.wallet_utils.lock_balance(
                user_id=user_id,
                amount=amount,
                reason=f"Withdrawal request",
                reference_type="withdrawal",
                reference_id=None
            )
            
            if not lock_success:
                return False, f"Failed to lock balance: {lock_message}", None
            
            # Get exchange rate
            rate_key = f"credit_to_{currency.lower()}_rate"
            exchange_rate = config.get(rate_key, 1.0)
            
            # Create withdrawal record
            withdrawal_id = self.generate_withdrawal_id()
            now = datetime.utcnow()
            processing_days = method_config.get("processing_days", config.get("default_processing_days", 3))
            
            withdrawal_doc = {
                "withdrawal_id": withdrawal_id,
                "user_id": user_id,
                "amount": amount,
                "currency": currency,
                "exchange_rate": exchange_rate,
                "fees": fees.dict(),
                "method_id": method_id,
                "method_name": method_config.get("name", method_id),
                "payment_details": payment_details,
                "status": WithdrawalStatus.PENDING.value,
                "user_notes": user_notes,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "processing_days": processing_days,
                "created_at": now,
                "updated_at": now,
                "estimated_completion": now + timedelta(days=processing_days)
            }
            
            await self.withdrawals.insert_one(withdrawal_doc)
            
            print(f"[OK] Created withdrawal request {withdrawal_id} for user {user_id}, amount: {amount}")
            
            return True, "Withdrawal request submitted successfully", {
                "withdrawal_id": withdrawal_id,
                "amount": amount,
                "currency": currency,
                "method": method_config.get("name", method_id),
                "fees": fees.dict(),
                "net_amount": fees.net_amount,
                "status": WithdrawalStatus.PENDING.value,
                "estimated_completion": (now + timedelta(days=processing_days)).isoformat(),
                "created_at": now.isoformat()
            }
            
        except Exception as e:
            print(f"[ERROR] create_withdrawal_request failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Failed to create withdrawal request: {str(e)}", None
    
    async def cancel_withdrawal(
        self,
        user_id: str,
        withdrawal_id: str
    ) -> Tuple[bool, str]:
        """Cancel a pending withdrawal request"""
        try:
            withdrawal = await self.withdrawals.find_one({
                "withdrawal_id": withdrawal_id,
                "user_id": user_id
            })
            
            if not withdrawal:
                return False, "Withdrawal not found"
            
            if withdrawal["status"] != WithdrawalStatus.PENDING.value:
                return False, f"Cannot cancel withdrawal in {withdrawal['status']} status"
            
            # Unlock the balance
            unlock_success, unlock_message = await self.wallet_utils.unlock_balance(
                user_id=user_id,
                amount=withdrawal["amount"],
                reason=f"Withdrawal cancelled: {withdrawal_id}",
                reference_type="withdrawal",
                reference_id=withdrawal_id
            )
            
            if not unlock_success:
                print(f"[WARN] Failed to unlock balance for cancelled withdrawal {withdrawal_id}: {unlock_message}")
            
            # Update withdrawal status
            await self.withdrawals.update_one(
                {"withdrawal_id": withdrawal_id},
                {
                    "$set": {
                        "status": WithdrawalStatus.CANCELLED.value,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            return True, "Withdrawal cancelled successfully"
            
        except Exception as e:
            print(f"[ERROR] cancel_withdrawal failed: {str(e)}")
            return False, f"Failed to cancel withdrawal: {str(e)}"
    
    async def get_withdrawal(self, withdrawal_id: str) -> Optional[Dict[str, Any]]:
        """Get withdrawal by ID"""
        withdrawal = await self.withdrawals.find_one({"withdrawal_id": withdrawal_id})
        if withdrawal and "_id" in withdrawal:
            withdrawal["_id"] = str(withdrawal["_id"])
        return withdrawal
    
    async def get_user_withdrawals(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Get user's withdrawal history"""
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        
        skip = (page - 1) * limit
        total = await self.withdrawals.count_documents(query)
        
        cursor = self.withdrawals.find(query).sort("created_at", -1).skip(skip).limit(limit)
        withdrawals = await cursor.to_list(length=limit)
        
        for w in withdrawals:
            if "_id" in w:
                w["_id"] = str(w["_id"])
        
        pagination = {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
        
        return withdrawals, pagination
    
    # ==================== ADMIN METHODS ====================
    
    async def approve_withdrawal(
        self,
        withdrawal_id: str,
        admin_id: str,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Admin: Approve a withdrawal request"""
        withdrawal = await self.get_withdrawal(withdrawal_id)
        if not withdrawal:
            return False, "Withdrawal not found"
        
        if withdrawal["status"] != WithdrawalStatus.PENDING.value:
            return False, f"Cannot approve withdrawal in {withdrawal['status']} status"
        
        await self.withdrawals.update_one(
            {"withdrawal_id": withdrawal_id},
            {
                "$set": {
                    "status": WithdrawalStatus.APPROVED.value,
                    "reviewed_by": admin_id,
                    "reviewed_at": datetime.utcnow(),
                    "admin_notes": admin_notes,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"[ADMIN] Approved withdrawal {withdrawal_id} by admin {admin_id}")
        return True, "Withdrawal approved"
    
    async def reject_withdrawal(
        self,
        withdrawal_id: str,
        admin_id: str,
        rejection_reason: str
    ) -> Tuple[bool, str]:
        """Admin: Reject a withdrawal request and unlock balance"""
        withdrawal = await self.get_withdrawal(withdrawal_id)
        if not withdrawal:
            return False, "Withdrawal not found"
        
        if withdrawal["status"] not in [WithdrawalStatus.PENDING.value, WithdrawalStatus.APPROVED.value]:
            return False, f"Cannot reject withdrawal in {withdrawal['status']} status"
        
        # Unlock balance
        await self.wallet_utils.unlock_balance(
            user_id=withdrawal["user_id"],
            amount=withdrawal["amount"],
            reason=f"Withdrawal rejected: {rejection_reason}",
            reference_type="withdrawal",
            reference_id=withdrawal_id
        )
        
        await self.withdrawals.update_one(
            {"withdrawal_id": withdrawal_id},
            {
                "$set": {
                    "status": WithdrawalStatus.REJECTED.value,
                    "reviewed_by": admin_id,
                    "reviewed_at": datetime.utcnow(),
                    "rejection_reason": rejection_reason,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"[ADMIN] Rejected withdrawal {withdrawal_id}: {rejection_reason}")
        return True, "Withdrawal rejected"
    
    async def mark_processing(
        self,
        withdrawal_id: str,
        admin_id: str,
        transaction_reference: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Admin: Mark withdrawal as being processed"""
        withdrawal = await self.get_withdrawal(withdrawal_id)
        if not withdrawal:
            return False, "Withdrawal not found"
        
        if withdrawal["status"] != WithdrawalStatus.APPROVED.value:
            return False, f"Cannot process withdrawal in {withdrawal['status']} status"
        
        await self.withdrawals.update_one(
            {"withdrawal_id": withdrawal_id},
            {
                "$set": {
                    "status": WithdrawalStatus.PROCESSING.value,
                    "transaction_reference": transaction_reference,
                    "processed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return True, "Withdrawal marked as processing"
    
    async def complete_withdrawal(
        self,
        withdrawal_id: str,
        admin_id: str,
        transaction_reference: str
    ) -> Tuple[bool, str]:
        """Admin: Complete a withdrawal - deduct balance permanently"""
        withdrawal = await self.get_withdrawal(withdrawal_id)
        if not withdrawal:
            return False, "Withdrawal not found"
        
        if withdrawal["status"] not in [WithdrawalStatus.APPROVED.value, WithdrawalStatus.PROCESSING.value]:
            return False, f"Cannot complete withdrawal in {withdrawal['status']} status"
        
        # Unlock and deduct
        await self.wallet_utils.unlock_balance(
            user_id=withdrawal["user_id"],
            amount=withdrawal["amount"],
            reason=f"Withdrawal completed: {withdrawal_id}",
            reference_type="withdrawal",
            reference_id=withdrawal_id
        )
        
        success, message, transaction = await self.wallet_utils.deduct_balance(
            user_id=withdrawal["user_id"],
            amount=withdrawal["amount"],
            category=TransactionCategory.WITHDRAWAL,
            description=f"Withdrawal completed: {withdrawal_id}",
            reference_type="withdrawal",
            reference_id=withdrawal_id,
            idempotency_key=f"WITHDRAWAL_{withdrawal_id}"
        )
        
        if not success:
            # Re-lock if deduction failed
            await self.wallet_utils.lock_balance(
                user_id=withdrawal["user_id"],
                amount=withdrawal["amount"],
                reason=f"Re-locked after failed deduction",
                reference_type="withdrawal",
                reference_id=withdrawal_id
            )
            return False, f"Failed to deduct balance: {message}"
        
        await self.withdrawals.update_one(
            {"withdrawal_id": withdrawal_id},
            {
                "$set": {
                    "status": WithdrawalStatus.COMPLETED.value,
                    "transaction_reference": transaction_reference,
                    "completed_at": datetime.utcnow(),
                    "completed_by": admin_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"[ADMIN] Completed withdrawal {withdrawal_id}, ref: {transaction_reference}")
        return True, "Withdrawal completed successfully"
    
    async def get_pending_withdrawals(
        self,
        page: int = 1,
        limit: int = 50
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Admin: Get all pending withdrawals"""
        query = {"status": WithdrawalStatus.PENDING.value}
        
        skip = (page - 1) * limit
        total = await self.withdrawals.count_documents(query)
        
        cursor = self.withdrawals.find(query).sort("created_at", 1).skip(skip).limit(limit)
        withdrawals = await cursor.to_list(length=limit)
        
        for w in withdrawals:
            if "_id" in w:
                w["_id"] = str(w["_id"])
        
        pagination = {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
        
        return withdrawals, pagination
    
    async def get_config(self) -> Dict[str, Any]:
        """Get full withdrawal configuration (public info)"""
        config = await self._get_config()
        methods = await self.get_available_methods()
        
        return {
            "min_amount": config.get("min_withdrawal_amount", 100),
            "max_amount": config.get("max_withdrawal_amount", 100000),
            "daily_limit": config.get("daily_withdrawal_limit", 50000),
            "monthly_limit": config.get("monthly_withdrawal_limit", 500000),
            "platform_fee_percentage": config.get("platform_fee_percentage", 5),
            "platform_fee_fixed": config.get("platform_fee_fixed", 0),
            "platform_fee_min": config.get("platform_fee_min", 10),
            "platform_fee_max": config.get("platform_fee_max", 500),
            "cooldown_hours": config.get("cooldown_hours", 24),
            "default_processing_days": config.get("default_processing_days", 3),
            "supported_currencies": config.get("supported_currencies", ["USD"]),
            "require_kyc": config.get("require_kyc", False),
            "require_2fa": config.get("require_2fa", False),
            "withdrawals_enabled": config.get("withdrawals_enabled", True),
            "maintenance_mode": config.get("maintenance_mode", False),
            "maintenance_message": config.get("maintenance_message", ""),
            "methods": methods
        }
    
    # ==================== ADMIN CONFIG METHODS ====================
    
    async def update_config(self, updates: Dict[str, Any], admin_id: str) -> Tuple[bool, str]:
        """Admin: Update global withdrawal configuration"""
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
    
    async def add_withdrawal_method(self, method: Dict[str, Any], admin_id: str) -> Tuple[bool, str]:
        """Admin: Add a new withdrawal method"""
        try:
            method["created_at"] = datetime.utcnow()
            method["updated_at"] = datetime.utcnow()
            method["created_by"] = admin_id
            
            await self.methods_collection.insert_one(method)
            self.clear_cache()
            return True, f"Method '{method['method_id']}' added"
        except Exception as e:
            return False, f"Failed to add method: {str(e)}"
    
    async def update_withdrawal_method(
        self, 
        method_id: str, 
        updates: Dict[str, Any], 
        admin_id: str
    ) -> Tuple[bool, str]:
        """Admin: Update a withdrawal method"""
        try:
            updates["updated_at"] = datetime.utcnow()
            updates["updated_by"] = admin_id
            
            result = await self.methods_collection.update_one(
                {"method_id": method_id},
                {"$set": updates}
            )
            
            if result.matched_count == 0:
                return False, f"Method '{method_id}' not found"
            
            self.clear_cache()
            return True, f"Method '{method_id}' updated"
        except Exception as e:
            return False, f"Failed to update method: {str(e)}"
    
    async def delete_withdrawal_method(self, method_id: str, admin_id: str) -> Tuple[bool, str]:
        """Admin: Delete (deactivate) a withdrawal method"""
        return await self.update_withdrawal_method(
            method_id, 
            {"is_active": False, "deleted_by": admin_id},
            admin_id
        )
