"""
Dynamic Contest Configuration Models
All settings stored in database - fully configurable
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ContestFeeConfig(BaseModel):
    """
    Global contest creation fee configuration.
    Stored in contest_config collection (single document).
    """
    config_id: str = "global"                   # Always "global" for single config
    
    # Contest Creation Fees
    creation_fee_type: str = "percentage"       # "fixed", "percentage", "mixed"
    creation_fee_percentage: float = 5.0        # % of prize pool as platform fee
    creation_fee_fixed: float = 0.0             # Fixed platform fee
    creation_fee_min: float = 10.0              # Minimum platform fee
    creation_fee_max: float = 1000.0            # Maximum platform fee (0 = no cap)
    
    # Prize Pool Requirements
    min_prize_pool: float = 100.0               # Minimum prize pool
    max_prize_pool: float = 1000000.0           # Maximum prize pool
    
    # Contest Limits
    max_active_contests_per_user: int = 5       # Max active contests a user can have
    max_participants_limit: int = 10000         # Max participants allowed per contest
    min_participants: int = 2                   # Minimum participants required
    
    # Entry Fee Settings (for participants)
    entry_fee_enabled: bool = True              # Allow contest creators to set entry fees
    entry_fee_max_percentage: float = 50.0      # Max entry fee as % of prize pool
    entry_fee_platform_cut: float = 10.0        # Platform cut from entry fees (%)
    
    # Refund Policy
    refund_on_cancel: bool = True               # Refund credits if contest is cancelled
    refund_percentage: float = 95.0             # % refunded (5% kept as cancellation fee)
    min_time_before_cancel: int = 24            # Hours before start when cancel is allowed
    
    # Prize Distribution
    auto_distribute_prizes: bool = False        # Auto-distribute or manual by admin
    prize_hold_days: int = 7                    # Days to hold prizes before release
    
    # Feature Flags
    contest_creation_enabled: bool = True       # Global kill switch
    require_kyc_for_creation: bool = False      # Require KYC to create contests
    require_email_verified: bool = True         # Require verified email
    min_account_age_days: int = 0               # Minimum account age to create
    
    # Maintenance
    maintenance_mode: bool = False
    maintenance_message: str = ""
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContestFeeCalculation(BaseModel):
    """Fee calculation result"""
    prize_pool: float                           # Contest prize pool
    platform_fee_percentage: float              # Applied percentage
    platform_fee_fixed: float                   # Applied fixed fee
    platform_fee_total: float                   # Total platform fee
    total_required: float                       # Prize pool + platform fee
    currency: str = "credits"


class ContestCreationValidation(BaseModel):
    """Validation result for contest creation"""
    can_create: bool
    reason: Optional[str] = None
    fee_breakdown: Optional[ContestFeeCalculation] = None
    user_balance: float = 0.0
    active_contests: int = 0
