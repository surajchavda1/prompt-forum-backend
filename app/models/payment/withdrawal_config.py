"""
Dynamic Withdrawal Configuration Models
All settings stored in database - fully configurable
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class WithdrawalMethodConfig(BaseModel):
    """
    Configuration for a single withdrawal payment method.
    Stored in withdrawal_methods collection.
    """
    method_id: str                              # Unique ID (bank_transfer, paypal, etc.)
    name: str                                   # Display name
    description: str = ""
    
    # Availability
    is_active: bool = True
    supported_currencies: List[str] = ["USD"]   # Currencies this method supports
    supported_countries: List[str] = []         # Empty = all countries
    
    # Fees (dynamic per method)
    fee_type: str = "fixed"                     # "fixed", "percentage", "mixed"
    fee_fixed: float = 0.0                      # Fixed fee amount
    fee_percentage: float = 0.0                 # Percentage fee
    fee_min: float = 0.0                        # Minimum fee
    fee_max: float = 0.0                        # Maximum fee (0 = no cap)
    
    # Limits per method
    min_amount: float = 10.0                    # Minimum withdrawal via this method
    max_amount: float = 100000.0                # Maximum per transaction
    
    # Processing
    processing_days: int = 3                    # Estimated processing time
    requires_verification: bool = False         # Requires extra verification
    
    # Display
    icon: Optional[str] = None                  # Icon URL or name
    sort_order: int = 0                         # Display order
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WithdrawalGlobalConfig(BaseModel):
    """
    Global withdrawal configuration.
    Stored in withdrawal_config collection (single document).
    """
    config_id: str = "global"                   # Always "global" for single config
    
    # Global Limits
    min_withdrawal_amount: float = 100.0        # Minimum credits to withdraw
    max_withdrawal_amount: float = 100000.0     # Maximum per request
    daily_withdrawal_limit: float = 50000.0     # Daily limit per user
    monthly_withdrawal_limit: float = 500000.0  # Monthly limit per user
    max_pending_requests: int = 3               # Max pending requests per user
    
    # Platform Fees (applied on top of method fees)
    platform_fee_percentage: float = 5.0        # Platform fee %
    platform_fee_fixed: float = 0.0             # Platform fixed fee
    platform_fee_min: float = 10.0              # Minimum total fee
    platform_fee_max: float = 500.0             # Maximum total fee (0 = no cap)
    
    # Exchange Rates (credits to currency)
    credit_to_usd_rate: float = 1.0             # 1 credit = X USD
    credit_to_inr_rate: float = 83.0            # 1 credit = X INR
    credit_to_eur_rate: float = 0.92            # 1 credit = X EUR
    credit_to_gbp_rate: float = 0.79            # 1 credit = X GBP
    
    # Security Settings
    cooldown_hours: int = 24                    # Hours between withdrawals
    require_kyc: bool = True                    # Require KYC verification
    require_2fa: bool = False                   # Require 2FA for withdrawal
    require_email_verification: bool = True    # Email OTP for withdrawal
    min_account_age_days: int = 0               # Minimum account age
    min_successful_payments: int = 0            # Minimum successful payments before withdrawal
    
    # Processing Settings
    auto_approve_threshold: float = 0.0         # Auto-approve below this amount (0 = never)
    default_processing_days: int = 3            # Default processing time
    
    # Supported Currencies
    supported_currencies: List[str] = ["USD", "EUR", "GBP", "INR", "USDT", "USDC"]
    default_currency: str = "USD"
    
    # Feature Flags
    withdrawals_enabled: bool = True            # Global kill switch
    new_user_withdrawals_enabled: bool = True   # New users can withdraw
    maintenance_mode: bool = False              # Pause all withdrawals
    maintenance_message: str = ""               # Message during maintenance
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WithdrawalMethodResponse(BaseModel):
    """Response format for withdrawal methods"""
    method_id: str
    name: str
    description: str
    supported_currencies: List[str]
    fee_type: str
    fee_fixed: float
    fee_percentage: float
    min_amount: float
    max_amount: float
    processing_days: int
    icon: Optional[str]
