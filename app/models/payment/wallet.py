"""
Wallet Models
Defines wallet structure and transaction types
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class WalletStatus(str, Enum):
    """Wallet status"""
    ACTIVE = "active"
    FROZEN = "frozen"
    SUSPENDED = "suspended"


class WalletInDB(BaseModel):
    """Wallet schema in database"""
    user_id: str
    balance: float = 0.0
    locked_balance: float = 0.0  # Balance locked for pending operations
    currency: str = "INR"
    status: WalletStatus = WalletStatus.ACTIVE
    total_credited: float = 0.0  # Lifetime credits added
    total_debited: float = 0.0   # Lifetime credits spent
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @classmethod
    def create(cls, user_id: str, currency: str = "INR"):
        """Create new wallet"""
        return cls(
            user_id=user_id,
            balance=0.0,
            locked_balance=0.0,
            currency=currency,
            status=WalletStatus.ACTIVE,
            total_credited=0.0,
            total_debited=0.0
        )


class WalletResponse(BaseModel):
    """Wallet response schema"""
    user_id: str
    balance: float
    locked_balance: float
    available_balance: float  # balance - locked_balance
    currency: str
    status: str
    total_credited: float
    total_debited: float


class WalletTopUpRequest(BaseModel):
    """Request to top up wallet"""
    amount: float = Field(..., gt=0, description="Amount to add (minimum 1)")
    package_id: Optional[str] = None  # Optional: use predefined package
    gateway: str = "cashfree"  # Payment gateway to use


class WalletWithdrawRequest(BaseModel):
    """Request to withdraw from wallet"""
    amount: float = Field(..., gt=0, description="Amount to withdraw")
    bank_account_id: Optional[str] = None  # For future bank transfer
