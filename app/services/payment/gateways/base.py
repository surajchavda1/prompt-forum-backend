"""
Base Payment Gateway
Abstract class defining the interface for all payment gateways
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PaymentStatus(str, Enum):
    """Standard payment status across all gateways"""
    CREATED = "created"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class PaymentOrderResult:
    """Result of creating a payment order"""
    success: bool
    order_id: str
    gateway_order_id: Optional[str] = None
    payment_link: Optional[str] = None
    payment_session_id: Optional[str] = None
    expires_at: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class PaymentStatusResult:
    """Result of checking payment status"""
    success: bool
    status: PaymentStatus
    gateway_payment_id: Optional[str] = None
    payment_method: Optional[str] = None
    paid_amount: Optional[float] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class WebhookVerificationResult:
    """Result of webhook verification"""
    is_valid: bool
    order_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    status: Optional[PaymentStatus] = None
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    error_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class RefundResult:
    """Result of refund operation"""
    success: bool
    refund_id: Optional[str] = None
    gateway_refund_id: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class BasePaymentGateway(ABC):
    """
    Abstract base class for payment gateways.
    All payment gateways must implement these methods.
    """
    
    gateway_id: str = "base"
    gateway_name: str = "Base Gateway"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize gateway with configuration.
        
        Args:
            config: Gateway configuration including API keys, endpoints, etc.
        """
        self.config = config
        self.is_sandbox = config.get("is_sandbox", True)
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        """Validate required configuration parameters"""
        pass
    
    @abstractmethod
    async def create_order(
        self,
        order_id: str,
        amount: float,
        currency: str,
        customer_id: str,
        customer_email: str,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        return_url: Optional[str] = None,
        notify_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentOrderResult:
        """
        Create a payment order.
        
        Args:
            order_id: Our internal order ID
            amount: Amount to charge
            currency: Currency code (INR, USD, etc.)
            customer_id: Customer's user ID
            customer_email: Customer's email
            customer_phone: Customer's phone (optional)
            customer_name: Customer's name (optional)
            return_url: URL to redirect after payment
            notify_url: Webhook URL for notifications
            metadata: Additional metadata
            
        Returns:
            PaymentOrderResult with order details
        """
        pass
    
    @abstractmethod
    async def get_order_status(
        self,
        gateway_order_id: str
    ) -> PaymentStatusResult:
        """
        Get payment order status.
        
        Args:
            gateway_order_id: Gateway's order ID
            
        Returns:
            PaymentStatusResult with current status
        """
        pass
    
    @abstractmethod
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        raw_body: bytes
    ) -> WebhookVerificationResult:
        """
        Verify webhook signature and extract data.
        
        Args:
            headers: Request headers
            raw_body: Raw request body (bytes)
            
        Returns:
            WebhookVerificationResult with verification status and data
        """
        pass
    
    @abstractmethod
    async def initiate_refund(
        self,
        gateway_order_id: str,
        refund_amount: float,
        refund_id: str,
        reason: Optional[str] = None
    ) -> RefundResult:
        """
        Initiate a refund.
        
        Args:
            gateway_order_id: Gateway's order ID
            refund_amount: Amount to refund
            refund_id: Our internal refund ID
            reason: Reason for refund
            
        Returns:
            RefundResult with refund details
        """
        pass
    
    def calculate_fees(self, amount: float) -> Tuple[float, float, float]:
        """
        Calculate fees for a given amount.
        
        Args:
            amount: Base amount
            
        Returns:
            Tuple of (platform_fee, gateway_fee, total_amount)
        """
        platform_fee_pct = self.config.get("platform_fee_percentage", 0.0)
        platform_fee_fixed = self.config.get("platform_fee_fixed", 0.0)
        gateway_fee_pct = self.config.get("gateway_fee_percentage", 0.0)
        gateway_fee_fixed = self.config.get("gateway_fee_fixed", 0.0)
        
        platform_fee = (amount * platform_fee_pct / 100) + platform_fee_fixed
        gateway_fee = (amount * gateway_fee_pct / 100) + gateway_fee_fixed
        total = amount + platform_fee + gateway_fee
        
        return round(platform_fee, 2), round(gateway_fee, 2), round(total, 2)
    
    def get_api_url(self, endpoint: str) -> str:
        """Get full API URL for endpoint"""
        base_url = self.config.get("sandbox_url" if self.is_sandbox else "production_url", "")
        return f"{base_url}/{endpoint.lstrip('/')}"
