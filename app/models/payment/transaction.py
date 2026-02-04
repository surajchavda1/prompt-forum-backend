"""
Transaction Models
Defines all transaction types and structures
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TransactionType(str, Enum):
    """Transaction type"""
    CREDIT = "credit"           # Money added to wallet
    DEBIT = "debit"             # Money deducted from wallet
    REFUND = "refund"           # Money refunded
    TRANSFER_IN = "transfer_in" # Transfer received
    TRANSFER_OUT = "transfer_out" # Transfer sent
    LOCK = "lock"               # Balance locked
    UNLOCK = "unlock"           # Balance unlocked


class TransactionStatus(str, Enum):
    """Transaction status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"
    EXPIRED = "expired"


class TransactionCategory(str, Enum):
    """Transaction category for reporting"""
    TOPUP = "topup"                 # Wallet top-up via payment
    CONTEST_ENTRY = "contest_entry" # Contest entry fee
    CONTEST_CREATE = "contest_create" # Contest creation fee
    CONTEST_PRIZE = "contest_prize"  # Contest prize won
    WITHDRAWAL = "withdrawal"        # Withdrawal to bank
    BONUS = "bonus"                  # Bonus credits
    REFUND = "refund"               # Refund
    ADMIN_CREDIT = "admin_credit"   # Admin credited
    ADMIN_DEBIT = "admin_debit"     # Admin debited


class TransactionInDB(BaseModel):
    """Transaction schema in database"""
    transaction_id: str  # Unique transaction ID (UUID)
    user_id: str
    wallet_id: str
    type: TransactionType
    category: TransactionCategory
    amount: float
    balance_before: float
    balance_after: float
    currency: str = "INR"
    status: TransactionStatus = TransactionStatus.PENDING
    
    # Reference info
    reference_type: Optional[str] = None  # "payment_order", "contest", etc.
    reference_id: Optional[str] = None    # ID of related entity
    
    # Payment gateway info (if applicable)
    gateway: Optional[str] = None
    gateway_transaction_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    
    # Metadata
    description: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Idempotency
    idempotency_key: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class TransactionResponse(BaseModel):
    """Transaction response schema"""
    transaction_id: str
    type: str
    category: str
    amount: float
    balance_after: float
    currency: str
    status: str
    description: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    created_at: datetime


class TransactionListResponse(BaseModel):
    """Transaction list response"""
    transactions: list
    pagination: Dict[str, Any]
