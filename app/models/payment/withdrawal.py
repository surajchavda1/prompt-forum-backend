"""
Withdrawal Models
Supports worldwide withdrawal methods
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class WithdrawalStatus(str, Enum):
    """Withdrawal request status"""
    PENDING = "pending"           # User submitted, awaiting review
    APPROVED = "approved"         # Admin approved, ready for processing
    PROCESSING = "processing"     # Payment being processed
    COMPLETED = "completed"       # Payment sent successfully
    REJECTED = "rejected"         # Admin rejected
    CANCELLED = "cancelled"       # User cancelled
    FAILED = "failed"             # Payment failed


class PaymentMethodType(str, Enum):
    """Supported worldwide payment methods"""
    # Bank Transfers
    BANK_TRANSFER = "bank_transfer"         # International bank transfer (SWIFT/IBAN)
    WIRE_TRANSFER = "wire_transfer"         # Wire transfer
    ACH = "ach"                             # US ACH transfer
    SEPA = "sepa"                           # EU SEPA transfer
    
    # Digital Wallets
    PAYPAL = "paypal"
    WISE = "wise"                           # TransferWise
    PAYONEER = "payoneer"
    SKRILL = "skrill"
    
    # Crypto
    CRYPTO_USDT = "crypto_usdt"             # USDT (Tether)
    CRYPTO_USDC = "crypto_usdc"             # USDC
    CRYPTO_BTC = "crypto_btc"               # Bitcoin
    CRYPTO_ETH = "crypto_eth"               # Ethereum
    
    # Regional
    UPI = "upi"                             # India UPI
    IMPS = "imps"                           # India IMPS
    NEFT = "neft"                           # India NEFT
    ALIPAY = "alipay"                       # China Alipay
    WECHAT_PAY = "wechat_pay"               # China WeChat Pay
    
    # Other
    CHECK = "check"                         # Physical check
    OTHER = "other"


class CurrencyCode(str, Enum):
    """Supported currencies for withdrawal"""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    INR = "INR"
    AUD = "AUD"
    CAD = "CAD"
    JPY = "JPY"
    CNY = "CNY"
    SGD = "SGD"
    AED = "AED"
    USDT = "USDT"     # Crypto stablecoins
    USDC = "USDC"
    BTC = "BTC"
    ETH = "ETH"


class BankDetails(BaseModel):
    """Bank account details for bank transfers"""
    account_holder_name: str
    bank_name: str
    account_number: str
    routing_number: Optional[str] = None    # US routing number
    swift_code: Optional[str] = None        # International SWIFT/BIC
    iban: Optional[str] = None              # International IBAN
    ifsc_code: Optional[str] = None         # India IFSC
    sort_code: Optional[str] = None         # UK sort code
    bsb_code: Optional[str] = None          # Australia BSB
    branch_name: Optional[str] = None
    branch_address: Optional[str] = None
    bank_country: str                       # ISO country code (US, IN, GB, etc.)


class DigitalWalletDetails(BaseModel):
    """Digital wallet details (PayPal, Wise, etc.)"""
    wallet_type: PaymentMethodType
    email: Optional[str] = None             # PayPal, Wise email
    phone: Optional[str] = None             # Some wallets use phone
    account_id: Optional[str] = None        # Payoneer ID, etc.
    account_holder_name: str


class CryptoWalletDetails(BaseModel):
    """Cryptocurrency wallet details"""
    currency: str                           # BTC, ETH, USDT, USDC
    network: str                            # ERC20, TRC20, BEP20, etc.
    wallet_address: str
    memo_tag: Optional[str] = None          # For some coins like XRP


class UPIDetails(BaseModel):
    """India UPI details"""
    upi_id: str                             # example@upi
    account_holder_name: str


class PaymentMethodDetails(BaseModel):
    """Unified payment method details"""
    method_type: PaymentMethodType
    currency: CurrencyCode
    country: str                            # ISO country code
    
    # One of these will be populated based on method_type
    bank_details: Optional[BankDetails] = None
    digital_wallet: Optional[DigitalWalletDetails] = None
    crypto_wallet: Optional[CryptoWalletDetails] = None
    upi_details: Optional[UPIDetails] = None
    
    # Verification status
    is_verified: bool = False
    verified_at: Optional[datetime] = None


class WithdrawalFees(BaseModel):
    """Fee breakdown for withdrawal"""
    withdrawal_amount: float                # Original amount requested
    platform_fee_percentage: float          # Platform fee %
    platform_fee_fixed: float               # Platform fixed fee
    platform_fee_total: float               # Total platform fee
    gateway_fee: float                      # Payment gateway/bank fee
    total_fees: float                       # All fees combined
    net_amount: float                       # Amount user will receive
    currency: str                           # Currency of withdrawal


class WithdrawalRequest(BaseModel):
    """Withdrawal request schema"""
    amount: float = Field(..., gt=0, description="Amount to withdraw in credits")
    payment_method: PaymentMethodDetails
    notes: Optional[str] = None             # User notes


class WithdrawalInDB(BaseModel):
    """Withdrawal record in database"""
    withdrawal_id: str                      # Unique ID (WD_xxxx)
    user_id: str
    
    # Amount details
    amount: float                           # Credits requested
    currency: str                           # Target currency
    exchange_rate: float = 1.0              # Credits to currency rate
    
    # Fee breakdown
    fees: WithdrawalFees
    
    # Payment details
    payment_method: PaymentMethodDetails
    
    # Status tracking
    status: WithdrawalStatus = WithdrawalStatus.PENDING
    
    # Admin actions
    reviewed_by: Optional[str] = None       # Admin user ID
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Processing details
    transaction_reference: Optional[str] = None  # External payment reference
    processed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # User notes and admin notes
    user_notes: Optional[str] = None
    admin_notes: Optional[str] = None
    
    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WithdrawalResponse(BaseModel):
    """Withdrawal response for API"""
    withdrawal_id: str
    amount: float
    currency: str
    fees: WithdrawalFees
    payment_method_type: str
    status: str
    created_at: str
    estimated_completion: Optional[str] = None


class WithdrawalListResponse(BaseModel):
    """List of withdrawals response"""
    withdrawals: List[WithdrawalResponse]
    pagination: Dict[str, Any]


# NOTE: WithdrawalConfig has been moved to withdrawal_config.py for dynamic DB-based configuration
# The static class below is DEPRECATED - use WithdrawalGlobalConfig from withdrawal_config.py instead
# All withdrawal settings are now loaded dynamically from the database.
