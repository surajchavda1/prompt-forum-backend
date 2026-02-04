"""
Payment Gateway Configuration Models
Dynamic gateway configuration
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class GatewayStatus(str, Enum):
    """Gateway status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class PaymentGatewayConfig(BaseModel):
    """Payment gateway configuration in database"""
    gateway_id: str         # cashfree, razorpay, stripe, etc.
    name: str               # Display name
    description: str = ""
    
    # Status
    status: GatewayStatus = GatewayStatus.ACTIVE
    is_default: bool = False
    
    # Fees (dynamic)
    platform_fee_percentage: float = 0.0  # Platform fee %
    platform_fee_fixed: float = 0.0       # Fixed platform fee
    gateway_fee_percentage: float = 0.0   # Gateway fee %
    gateway_fee_fixed: float = 0.0        # Fixed gateway fee
    
    # Limits
    min_amount: float = 1.0
    max_amount: float = 100000.0
    
    # Supported features
    supports_refund: bool = True
    supports_partial_refund: bool = True
    supports_subscription: bool = False
    
    # Supported currencies
    supported_currencies: List[str] = ["INR"]
    
    # Environment
    is_sandbox: bool = True  # True = test mode
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GatewayConfigResponse(BaseModel):
    """Gateway configuration response (public)"""
    gateway_id: str
    name: str
    description: str
    status: str
    is_default: bool
    min_amount: float
    max_amount: float
    supported_currencies: List[str]
    platform_fee_percentage: float
    platform_fee_fixed: float


class GatewayListResponse(BaseModel):
    """Gateway list response"""
    gateways: List[GatewayConfigResponse]
    default_gateway: Optional[str]
