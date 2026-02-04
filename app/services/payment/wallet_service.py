"""
Wallet Service
High-level wallet operations
"""
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.utils.wallet import WalletUtils
from app.models.payment.wallet import WalletStatus, WalletResponse
from app.models.payment.transaction import TransactionCategory, TransactionType


class WalletService:
    """
    Service for wallet operations.
    Provides high-level API for wallet management.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.wallet_utils = WalletUtils(db)
        self.wallets = db.wallets
        self.transactions = db.wallet_transactions
    
    async def get_wallet(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's wallet with computed available balance.
        Creates wallet if not exists.
        """
        wallet = await self.wallet_utils.get_or_create_wallet(user_id)
        
        if wallet:
            # Add computed available balance
            wallet["available_balance"] = wallet.get("balance", 0.0) - wallet.get("locked_balance", 0.0)
        
        return wallet
    
    async def get_balance(self, user_id: str) -> Dict[str, float]:
        """
        Get user's balance summary.
        
        Returns:
            Dict with balance, locked_balance, available_balance
        """
        available, locked = await self.wallet_utils.get_balance(user_id)
        wallet = await self.wallet_utils.get_wallet(user_id)
        
        return {
            "balance": wallet.get("balance", 0.0) if wallet else 0.0,
            "locked_balance": locked,
            "available_balance": available,
            "currency": wallet.get("currency", "INR") if wallet else "INR"
        }
    
    async def credit_wallet(
        self,
        user_id: str,
        amount: float,
        category: TransactionCategory,
        description: str = "",
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        gateway: Optional[str] = None,
        gateway_transaction_id: Optional[str] = None,
        gateway_order_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Credit amount to user's wallet.
        
        Returns:
            (success, message, transaction)
        """
        return await self.wallet_utils.add_balance(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
            gateway=gateway,
            gateway_transaction_id=gateway_transaction_id,
            gateway_order_id=gateway_order_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )
    
    async def debit_wallet(
        self,
        user_id: str,
        amount: float,
        category: TransactionCategory,
        description: str = "",
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Debit amount from user's wallet.
        
        Returns:
            (success, message, transaction)
        """
        return await self.wallet_utils.deduct_balance(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )
    
    async def lock_balance(
        self,
        user_id: str,
        amount: float,
        reason: str = "",
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Lock balance for pending operation"""
        return await self.wallet_utils.lock_balance(
            user_id=user_id,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id
        )
    
    async def unlock_balance(
        self,
        user_id: str,
        amount: float,
        reason: str = "",
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Unlock previously locked balance"""
        return await self.wallet_utils.unlock_balance(
            user_id=user_id,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id
        )
    
    async def check_balance(self, user_id: str, required_amount: float) -> Tuple[bool, float]:
        """
        Check if user has sufficient balance.
        
        Returns:
            (has_sufficient, available_balance)
        """
        available, _ = await self.wallet_utils.get_balance(user_id)
        return available >= required_amount, available
    
    async def get_transaction_history(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        category: Optional[str] = None,
        transaction_type: Optional[str] = None
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        Get user's transaction history.
        
        Returns:
            (transactions, pagination_info)
        """
        # Convert string to enum if provided
        cat_enum = TransactionCategory(category) if category else None
        type_enum = TransactionType(transaction_type) if transaction_type else None
        
        transactions, total = await self.wallet_utils.get_transaction_history(
            user_id=user_id,
            page=page,
            limit=limit,
            category=cat_enum,
            transaction_type=type_enum
        )
        
        # Convert ObjectId to string for JSON serialization
        for txn in transactions:
            if "_id" in txn:
                txn["_id"] = str(txn["_id"])
        
        pagination = {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
        
        return transactions, pagination
    
    async def freeze_wallet(self, user_id: str, reason: str = "") -> Tuple[bool, str]:
        """
        Freeze user's wallet (admin action).
        Frozen wallets cannot transact.
        """
        result = await self.wallets.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "status": WalletStatus.FROZEN,
                    "frozen_reason": reason,
                    "frozen_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            return True, "Wallet frozen successfully"
        return False, "Wallet not found or already frozen"
    
    async def unfreeze_wallet(self, user_id: str) -> Tuple[bool, str]:
        """Unfreeze user's wallet (admin action)"""
        result = await self.wallets.update_one(
            {"user_id": user_id, "status": WalletStatus.FROZEN},
            {
                "$set": {
                    "status": WalletStatus.ACTIVE,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "frozen_reason": "",
                    "frozen_at": ""
                }
            }
        )
        
        if result.modified_count > 0:
            return True, "Wallet unfrozen successfully"
        return False, "Wallet not found or not frozen"
    
    async def get_wallet_stats(self, user_id: str) -> Dict[str, Any]:
        """Get wallet statistics for a user"""
        wallet = await self.get_wallet(user_id)
        
        if not wallet:
            return {}
        
        # Get transaction counts by category
        pipeline = [
            {"$match": {"user_id": user_id, "status": "completed"}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"}
            }}
        ]
        
        stats_cursor = self.transactions.aggregate(pipeline)
        category_stats = await stats_cursor.to_list(length=100)
        
        return {
            "balance": wallet.get("balance", 0.0),
            "available_balance": wallet.get("available_balance", 0.0),
            "locked_balance": wallet.get("locked_balance", 0.0),
            "total_credited": wallet.get("total_credited", 0.0),
            "total_debited": wallet.get("total_debited", 0.0),
            "currency": wallet.get("currency", "INR"),
            "status": wallet.get("status", "active"),
            "category_breakdown": {
                stat["_id"]: {
                    "count": stat["count"],
                    "total": stat["total_amount"]
                } for stat in category_stats
            }
        }
