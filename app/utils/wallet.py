"""
Wallet Utilities
Common wallet operations for database interactions
Atomic operations to ensure consistency
"""
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.models.payment.wallet import WalletStatus
from app.models.payment.transaction import (
    TransactionType, TransactionStatus, TransactionCategory
)


class WalletUtils:
    """
    Utility class for wallet operations.
    All operations are designed to be atomic and safe.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.wallets = db.wallets
        self.transactions = db.wallet_transactions
    
    @staticmethod
    def generate_transaction_id() -> str:
        """Generate unique transaction ID"""
        return f"TXN_{uuid.uuid4().hex[:16].upper()}"
    
    async def get_or_create_wallet(self, user_id: str, currency: str = "INR") -> Dict[str, Any]:
        """
        Get user's wallet or create if not exists.
        Thread-safe using upsert.
        Also migrates old wallet format to new format.
        """
        now = datetime.utcnow()
        
        result = await self.wallets.find_one_and_update(
            {"user_id": user_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "balance": 0.0,
                    "locked_balance": 0.0,
                    "currency": currency,
                    "status": WalletStatus.ACTIVE,
                    "total_credited": 0.0,
                    "total_debited": 0.0,
                    "created_at": now
                },
                "$set": {"updated_at": now}
            },
            upsert=True,
            return_document=True
        )
        
        # Migrate old wallet format if needed (is_active -> status)
        if result and result.get("status") is None and result.get("is_active") is not None:
            # Old format detected, migrate to new format
            await self.wallets.update_one(
                {"_id": result["_id"]},
                {
                    "$set": {
                        "status": WalletStatus.ACTIVE if result.get("is_active") else WalletStatus.SUSPENDED,
                        "total_credited": result.get("total_deposited", 0.0),
                        "total_debited": result.get("total_spent", 0.0),
                        "locked_balance": result.get("locked_balance", 0.0),
                    },
                    "$unset": {
                        "is_active": "",
                        "total_deposited": "",
                        "total_spent": ""
                    }
                }
            )
            # Fetch updated wallet
            result = await self.wallets.find_one({"_id": result["_id"]})
            print(f"[INFO] Migrated wallet for user {user_id} to new format")
        
        return result
    
    async def get_wallet(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's wallet"""
        return await self.wallets.find_one({"user_id": user_id})
    
    async def get_balance(self, user_id: str) -> Tuple[float, float]:
        """
        Get user's balance.
        Returns: (available_balance, locked_balance)
        """
        wallet = await self.get_or_create_wallet(user_id)
        balance = wallet.get("balance", 0.0)
        locked = wallet.get("locked_balance", 0.0)
        return balance - locked, locked
    
    async def add_balance(
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
        Add balance to user's wallet.
        
        Returns: (success, message, transaction)
        """
        if amount <= 0:
            return False, "Amount must be positive", None
        
        print(f"[DEBUG] add_balance called: user={user_id}, amount={amount}, idempotency_key={idempotency_key}")
        
        # Idempotency check - SECURITY: Prevent double crediting
        if idempotency_key:
            existing = await self.transactions.find_one({
                "idempotency_key": idempotency_key,
                "status": TransactionStatus.COMPLETED
            })
            if existing:
                print(f"[INFO] Idempotency check: Transaction already processed for key {idempotency_key}")
                return True, "Transaction already processed", existing
        
        # Get or create wallet (also handles migration)
        wallet = await self.get_or_create_wallet(user_id)
        print(f"[DEBUG] Wallet retrieved: {wallet.get('_id')}, balance={wallet.get('balance')}, status={wallet.get('status')}")
        
        # Check wallet status (handle both old 'is_active' and new 'status' fields)
        wallet_status = wallet.get("status")
        is_active_legacy = wallet.get("is_active", True)  # Old field
        
        # Wallet is active if: status == "active" OR (no status field AND is_active == true)
        is_wallet_active = (wallet_status == WalletStatus.ACTIVE) or (wallet_status is None and is_active_legacy)
        
        if not is_wallet_active:
            print(f"[ERROR] Wallet not active: status={wallet_status}, is_active={is_active_legacy}")
            return False, f"Wallet is not active (status: {wallet_status})", None
        
        wallet_id = str(wallet["_id"])
        balance_before = wallet.get("balance", 0.0)
        balance_after = balance_before + amount
        
        # Create transaction record
        transaction_id = self.generate_transaction_id()
        now = datetime.utcnow()
        
        transaction = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "wallet_id": wallet_id,
            "type": TransactionType.CREDIT,
            "category": category,
            "amount": amount,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "currency": wallet.get("currency", "INR"),
            "status": TransactionStatus.COMPLETED,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "gateway": gateway,
            "gateway_transaction_id": gateway_transaction_id,
            "gateway_order_id": gateway_order_id,
            "description": description or f"Credit of {amount}",
            "metadata": metadata or {},
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
            "completed_at": now
        }
        
        # Atomic update: balance + transaction
        try:
            # Update wallet balance
            update_result = await self.wallets.update_one(
                {"_id": wallet["_id"], "status": WalletStatus.ACTIVE},
                {
                    "$inc": {
                        "balance": amount,
                        "total_credited": amount
                    },
                    "$set": {"updated_at": now}
                }
            )
            
            if update_result.modified_count == 0:
                return False, "Failed to update wallet", None
            
            # Insert transaction
            await self.transactions.insert_one(transaction)
            
            return True, "Balance added successfully", transaction
            
        except Exception as e:
            # Log error
            print(f"[ERROR] add_balance failed: {str(e)}")
            return False, f"Transaction failed: {str(e)}", None
    
    async def deduct_balance(
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
        Deduct balance from user's wallet.
        Checks available balance before deducting.
        
        Returns: (success, message, transaction)
        """
        if amount <= 0:
            return False, "Amount must be positive", None
        
        # Idempotency check
        if idempotency_key:
            existing = await self.transactions.find_one({
                "idempotency_key": idempotency_key,
                "status": TransactionStatus.COMPLETED
            })
            if existing:
                return True, "Transaction already processed", existing
        
        # Get wallet (use get_or_create to trigger migration if needed)
        wallet = await self.get_or_create_wallet(user_id)
        if not wallet:
            return False, "Wallet not found", None
        
        # Check wallet status (handle both old and new formats)
        wallet_status = wallet.get("status")
        is_active_legacy = wallet.get("is_active", True)
        is_wallet_active = (wallet_status == WalletStatus.ACTIVE) or (wallet_status is None and is_active_legacy)
        
        if not is_wallet_active:
            return False, f"Wallet is not active (status: {wallet_status})", None
        
        # Check available balance
        balance = wallet.get("balance", 0.0)
        locked = wallet.get("locked_balance", 0.0)
        available = balance - locked
        
        if available < amount:
            return False, f"Insufficient balance. Available: {available}", None
        
        wallet_id = str(wallet["_id"])
        balance_after = balance - amount
        
        # Create transaction record
        transaction_id = self.generate_transaction_id()
        now = datetime.utcnow()
        
        transaction = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "wallet_id": wallet_id,
            "type": TransactionType.DEBIT,
            "category": category,
            "amount": amount,
            "balance_before": balance,
            "balance_after": balance_after,
            "currency": wallet.get("currency", "INR"),
            "status": TransactionStatus.COMPLETED,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "description": description or f"Debit of {amount}",
            "metadata": metadata or {},
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
            "completed_at": now
        }
        
        # Atomic update with balance check
        try:
            # Update wallet balance (only if sufficient)
            update_result = await self.wallets.update_one(
                {
                    "_id": wallet["_id"],
                    "status": WalletStatus.ACTIVE,
                    "$expr": {"$gte": [{"$subtract": ["$balance", "$locked_balance"]}, amount]}
                },
                {
                    "$inc": {
                        "balance": -amount,
                        "total_debited": amount
                    },
                    "$set": {"updated_at": now}
                }
            )
            
            if update_result.modified_count == 0:
                return False, "Insufficient balance or wallet locked", None
            
            # Insert transaction
            await self.transactions.insert_one(transaction)
            
            return True, "Balance deducted successfully", transaction
            
        except Exception as e:
            print(f"[ERROR] deduct_balance failed: {str(e)}")
            return False, f"Transaction failed: {str(e)}", None
    
    async def lock_balance(
        self,
        user_id: str,
        amount: float,
        reason: str = "",
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Lock a portion of balance for pending operations.
        Locked balance cannot be spent.
        
        Returns: (success, message)
        """
        if amount <= 0:
            return False, "Amount must be positive"
        
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return False, "Wallet not found"
        
        available = wallet.get("balance", 0.0) - wallet.get("locked_balance", 0.0)
        if available < amount:
            return False, f"Insufficient available balance. Available: {available}"
        
        now = datetime.utcnow()
        
        # Lock balance
        result = await self.wallets.update_one(
            {
                "_id": wallet["_id"],
                "$expr": {"$gte": [{"$subtract": ["$balance", "$locked_balance"]}, amount]}
            },
            {
                "$inc": {"locked_balance": amount},
                "$set": {"updated_at": now}
            }
        )
        
        if result.modified_count == 0:
            return False, "Failed to lock balance"
        
        # Log lock transaction
        transaction = {
            "transaction_id": self.generate_transaction_id(),
            "user_id": user_id,
            "wallet_id": str(wallet["_id"]),
            "type": TransactionType.LOCK,
            "category": TransactionCategory.CONTEST_ENTRY,  # Most common use
            "amount": amount,
            "balance_before": wallet.get("balance", 0.0),
            "balance_after": wallet.get("balance", 0.0),  # Balance doesn't change, just locked
            "currency": wallet.get("currency", "INR"),
            "status": TransactionStatus.COMPLETED,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "description": reason or f"Locked {amount} credits",
            "created_at": now,
            "updated_at": now,
            "completed_at": now
        }
        await self.transactions.insert_one(transaction)
        
        return True, "Balance locked successfully"
    
    async def unlock_balance(
        self,
        user_id: str,
        amount: float,
        reason: str = "",
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Unlock previously locked balance.
        
        Returns: (success, message)
        """
        if amount <= 0:
            return False, "Amount must be positive"
        
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return False, "Wallet not found"
        
        locked = wallet.get("locked_balance", 0.0)
        if locked < amount:
            return False, f"Cannot unlock {amount}. Only {locked} is locked"
        
        now = datetime.utcnow()
        
        # Unlock balance
        result = await self.wallets.update_one(
            {
                "_id": wallet["_id"],
                "locked_balance": {"$gte": amount}
            },
            {
                "$inc": {"locked_balance": -amount},
                "$set": {"updated_at": now}
            }
        )
        
        if result.modified_count == 0:
            return False, "Failed to unlock balance"
        
        # Log unlock transaction
        transaction = {
            "transaction_id": self.generate_transaction_id(),
            "user_id": user_id,
            "wallet_id": str(wallet["_id"]),
            "type": TransactionType.UNLOCK,
            "category": TransactionCategory.CONTEST_ENTRY,
            "amount": amount,
            "balance_before": wallet.get("balance", 0.0),
            "balance_after": wallet.get("balance", 0.0),
            "currency": wallet.get("currency", "INR"),
            "status": TransactionStatus.COMPLETED,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "description": reason or f"Unlocked {amount} credits",
            "created_at": now,
            "updated_at": now,
            "completed_at": now
        }
        await self.transactions.insert_one(transaction)
        
        return True, "Balance unlocked successfully"
    
    async def refund(
        self,
        user_id: str,
        amount: float,
        original_transaction_id: str,
        reason: str = ""
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Refund a previous transaction.
        
        Returns: (success, message, transaction)
        """
        # Add balance back as refund
        return await self.add_balance(
            user_id=user_id,
            amount=amount,
            category=TransactionCategory.REFUND,
            description=reason or f"Refund for transaction {original_transaction_id}",
            reference_type="transaction",
            reference_id=original_transaction_id,
            idempotency_key=f"REFUND_{original_transaction_id}"
        )
    
    async def get_transaction_history(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        category: Optional[TransactionCategory] = None,
        transaction_type: Optional[TransactionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[list, int]:
        """
        Get user's transaction history with filters.
        
        Returns: (transactions, total_count)
        """
        query = {"user_id": user_id}
        
        if category:
            query["category"] = category
        if transaction_type:
            query["type"] = transaction_type
        if start_date:
            query["created_at"] = {"$gte": start_date}
        if end_date:
            if "created_at" in query:
                query["created_at"]["$lte"] = end_date
            else:
                query["created_at"] = {"$lte": end_date}
        
        skip = (page - 1) * limit
        
        # Get total count
        total = await self.transactions.count_documents(query)
        
        # Get transactions
        cursor = self.transactions.find(query).sort("created_at", -1).skip(skip).limit(limit)
        transactions = await cursor.to_list(length=limit)
        
        return transactions, total


# Singleton-like helper functions for easy import
async def get_wallet_utils(db: AsyncIOMotorDatabase) -> WalletUtils:
    """Get WalletUtils instance"""
    return WalletUtils(db)
