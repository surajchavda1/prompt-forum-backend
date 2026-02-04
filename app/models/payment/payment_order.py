"""
Payment Order Models
Defines payment order structure for gateway transactions
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class PaymentOrderStatus(str, Enum):
    """Payment order status"""
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentOrderInDB(BaseModel):
    """Payment order in database"""
    order_id: str           # Our internal order ID
    user_id: str
    
    # Amount info
    amount: float           # Base amount
    credits: float          # Credits to be added
    fee: float = 0.0        # Platform fee
    gateway_fee: float = 0.0 # Gateway fee
    total_amount: float     # Total charged (amount + fees)
    currency: str = "INR"
    
    # Package info (if using predefined package)
    package_id: Optional[str] = None
    package_name: Optional[str] = None
    
    # Gateway info
    gateway: str            # cashfree, razorpay, etc.
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    gateway_response: Dict[str, Any] = Field(default_factory=dict)
    
    # Payment link/session
    payment_link: Optional[str] = None
    payment_session_id: Optional[str] = None
    
    # Status
    status: PaymentOrderStatus = PaymentOrderStatus.CREATED
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class PaymentOrderResponse(BaseModel):
    """Payment order response"""
    order_id: str
    amount: float
    credits: float
    total_amount: float
    currency: str
    gateway: str
    payment_link: Optional[str] = None
    payment_session_id: Optional[str] = None
    status: str
    expires_at: Optional[datetime] = None


class CreatePaymentOrderRequest(BaseModel):
    """Request to create payment order"""
    amount: float = Field(..., gt=0)
    gateway: str = "cashfree"
    package_id: Optional[str] = None
    return_url: Optional[str] = None


class PaymentWebhookData(BaseModel):
    """Webhook data from payment gateway"""
    order_id: str
    gateway_order_id: str
    gateway_payment_id: Optional[str] = None
    status: str
    amount: float
    currency: str = "INR"
    payment_method: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
