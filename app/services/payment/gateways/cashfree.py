"""
Cashfree Payment Gateway Implementation
Implements the BasePaymentGateway for Cashfree Payments
API Version: 2023-08-01 (Latest stable)
"""
import os
import hmac
import hashlib
import base64
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from app.services.payment.gateways.base import (
    BasePaymentGateway,
    PaymentOrderResult,
    PaymentStatusResult,
    WebhookVerificationResult,
    RefundResult,
    PaymentStatus
)

load_dotenv()


class CashfreeGateway(BasePaymentGateway):
    """
    Cashfree Payment Gateway Implementation
    
    Features:
    - Order creation with hosted checkout
    - Webhook signature verification (HMAC-SHA256)
    - Payment status polling
    - Refund support
    """
    
    gateway_id = "cashfree"
    gateway_name = "Cashfree Payments"
    
    # API Endpoints
    SANDBOX_URL = "https://sandbox.cashfree.com/pg"
    PRODUCTION_URL = "https://api.cashfree.com/pg"
    API_VERSION = "2022-09-01"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Cashfree gateway"""
        # Always load base config from environment (contains credentials)
        env_config = self._load_config_from_env()
        
        # Merge with provided config (override non-credential settings)
        if config is not None:
            # Credentials always come from env for security
            env_config.update({
                k: v for k, v in config.items() 
                if k not in ("app_id", "secret_key") and v is not None
            })
        
        config = env_config
        
        # Set URLs
        config["sandbox_url"] = self.SANDBOX_URL
        config["production_url"] = self.PRODUCTION_URL
        
        super().__init__(config)
        
        self.app_id = config.get("app_id")
        self.secret_key = config.get("secret_key")
        self.api_version = config.get("api_version", self.API_VERSION)
    
    def _load_config_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        # Force reload of .env file
        load_dotenv(override=True)
        
        app_id = os.getenv("CASHFREE_APP_ID")
        secret_key = os.getenv("CASHFREE_SECRET_KEY")
        
        # Debug logging
        if not app_id:
            print("[WARN] CASHFREE_APP_ID not found in environment")
        if not secret_key:
            print("[WARN] CASHFREE_SECRET_KEY not found in environment")
        
        return {
            "app_id": app_id,
            "secret_key": secret_key,
            "is_sandbox": os.getenv("CASHFREE_SANDBOX", "true").lower() == "true",
            "api_version": os.getenv("CASHFREE_API_VERSION", self.API_VERSION),
            "platform_fee_percentage": float(os.getenv("PAYMENT_PLATFORM_FEE_PERCENTAGE", "0")),
            "platform_fee_fixed": float(os.getenv("PAYMENT_PLATFORM_FEE_FIXED", "0")),
            "gateway_fee_percentage": float(os.getenv("CASHFREE_GATEWAY_FEE_PERCENTAGE", "2")),
            "gateway_fee_fixed": float(os.getenv("CASHFREE_GATEWAY_FEE_FIXED", "0")),
        }
    
    def _validate_config(self):
        """Validate required Cashfree configuration"""
        if not self.config.get("app_id"):
            raise ValueError("CASHFREE_APP_ID is required")
        if not self.config.get("secret_key"):
            raise ValueError("CASHFREE_SECRET_KEY is required")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Cashfree API requests"""
        return {
            "x-client-id": self.app_id,
            "x-client-secret": self.secret_key,
            "x-api-version": "2023-08-01",  # Stable version as per docs
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _map_status(self, cashfree_status: str) -> PaymentStatus:
        """Map Cashfree status to standard PaymentStatus"""
        status_map = {
            "ACTIVE": PaymentStatus.PENDING,
            "PAID": PaymentStatus.SUCCESS,
            "EXPIRED": PaymentStatus.EXPIRED,
            "CANCELLED": PaymentStatus.CANCELLED,
            "VOID": PaymentStatus.CANCELLED,
            "USER_DROPPED": PaymentStatus.CANCELLED,
            "PARTIALLY_PAID": PaymentStatus.PENDING,
        }
        return status_map.get(cashfree_status.upper(), PaymentStatus.PENDING)
    
    async def create_order(
        self,
        order_id: str,
        amount: float,
        currency: str = "INR",
        customer_id: str = None,
        customer_email: str = None,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        return_url: Optional[str] = None,
        notify_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentOrderResult:
        """
        Create a Cashfree payment order.
        Uses Cashfree's hosted checkout flow.
        """
        try:
            # Build customer details - EXACTLY as per Cashfree docs
            # Minimum required: customer_id, customer_phone
            customer_details = {
                "customer_id": customer_id or f"cust_{order_id}",
                "customer_phone": customer_phone or "9999999999",
            }
            
            # Add optional fields only if provided
            if customer_email:
                customer_details["customer_email"] = customer_email
            if customer_name:
                customer_details["customer_name"] = customer_name
            
            # Prepare MINIMAL request payload - exactly as per Cashfree docs
            # Reference: https://www.cashfree.com/docs/api-reference/payments/latest/orders/create
            payload = {
                "order_id": order_id,
                "order_amount": round(float(amount), 2),  # Up to 2 decimals as per docs
                "order_currency": "INR",  # REQUIRED
                "customer_details": customer_details,
            }
            
            # Add order_meta only if we have return_url or notify_url
            order_meta = {}
            if return_url:
                # Use Cashfree's {order_id} placeholder for return URL
                order_meta["return_url"] = return_url if "{order_id}" in return_url else f"{return_url}?order_id={{order_id}}"
            if notify_url:
                order_meta["notify_url"] = notify_url
            
            if order_meta:
                payload["order_meta"] = order_meta
            
            # Debug log
            print(f"[DEBUG] Cashfree create_order payload: {payload}")
            print(f"[DEBUG] Cashfree API URL: {self.get_api_url('/orders')}")
            print(f"[DEBUG] Cashfree headers: x-api-version={self._get_headers().get('x-api-version')}")
            
            # Make API request
            api_url = self.get_api_url("/orders")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    api_url,
                    headers=self._get_headers(),
                    json=payload
                )
                
                response_data = response.json()
                
                if response.status_code in [200, 201]:
                    # Success
                    # NOTE: Cashfree requires frontend JS SDK to open checkout
                    # The payment_session_id is used with their SDK, not as a direct URL
                    payment_session_id = response_data.get("payment_session_id")
                    
                    return PaymentOrderResult(
                        success=True,
                        order_id=order_id,
                        gateway_order_id=response_data.get("cf_order_id") or response_data.get("order_id"),
                        payment_link=None,  # Cashfree doesn't support direct URL - use SDK
                        payment_session_id=payment_session_id,
                        expires_at=response_data.get("order_expiry_time"),
                        raw_response=response_data
                    )
                else:
                    # Error
                    error_msg = response_data.get("message") or response_data.get("error", {}).get("message", "Unknown error")
                    return PaymentOrderResult(
                        success=False,
                        order_id=order_id,
                        error_message=error_msg,
                        raw_response=response_data
                    )
                    
        except Exception as e:
            return PaymentOrderResult(
                success=False,
                order_id=order_id,
                error_message=str(e)
            )
    
    async def get_order_status(
        self,
        gateway_order_id: str
    ) -> PaymentStatusResult:
        """Get payment order status from Cashfree"""
        try:
            api_url = self.get_api_url(f"/orders/{gateway_order_id}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    api_url,
                    headers=self._get_headers()
                )
                
                response_data = response.json()
                
                if response.status_code == 200:
                    order_status = response_data.get("order_status", "PENDING")
                    
                    # Get payment details if paid
                    payment_id = None
                    payment_method = None
                    paid_amount = None
                    
                    if order_status == "PAID":
                        # Fetch payments for this order
                        payments_url = self.get_api_url(f"/orders/{gateway_order_id}/payments")
                        payments_response = await client.get(
                            payments_url,
                            headers=self._get_headers()
                        )
                        
                        if payments_response.status_code == 200:
                            payments_data = payments_response.json()
                            if payments_data and len(payments_data) > 0:
                                latest_payment = payments_data[0]
                                payment_id = latest_payment.get("cf_payment_id")
                                payment_method = latest_payment.get("payment_method", {}).get("type")
                                paid_amount = latest_payment.get("payment_amount")
                    
                    return PaymentStatusResult(
                        success=True,
                        status=self._map_status(order_status),
                        gateway_payment_id=payment_id,
                        payment_method=payment_method,
                        paid_amount=paid_amount or response_data.get("order_amount"),
                        raw_response=response_data
                    )
                else:
                    error_msg = response_data.get("message", "Failed to get order status")
                    return PaymentStatusResult(
                        success=False,
                        status=PaymentStatus.PENDING,
                        error_message=error_msg,
                        raw_response=response_data
                    )
                    
        except Exception as e:
            return PaymentStatusResult(
                success=False,
                status=PaymentStatus.PENDING,
                error_message=str(e)
            )
    
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        raw_body: bytes
    ) -> WebhookVerificationResult:
        """
        Verify Cashfree webhook signature.
        
        Signature verification:
        1. Concatenate timestamp + raw body
        2. HMAC-SHA256 with secret key
        3. Base64 encode
        4. Compare with x-webhook-signature
        """
        try:
            # Get required headers (case-insensitive)
            headers_lower = {k.lower(): v for k, v in headers.items()}
            
            timestamp = headers_lower.get("x-webhook-timestamp")
            signature = headers_lower.get("x-webhook-signature")
            
            if not timestamp or not signature:
                return WebhookVerificationResult(
                    is_valid=False,
                    error_message="Missing webhook timestamp or signature headers"
                )
            
            # Compute signature
            sign_string = timestamp + raw_body.decode('utf-8')
            computed_signature = base64.b64encode(
                hmac.new(
                    self.secret_key.encode('utf-8'),
                    sign_string.encode('utf-8'),
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            # Verify signature
            if not hmac.compare_digest(computed_signature, signature):
                return WebhookVerificationResult(
                    is_valid=False,
                    error_message="Invalid webhook signature"
                )
            
            # Parse webhook data
            import json
            webhook_data = json.loads(raw_body)
            
            # Extract order and payment info
            # Webhook structure: { "data": { "order": {...}, "payment": {...} }, "type": "PAYMENT_SUCCESS_WEBHOOK" }
            data = webhook_data.get("data", {})
            order_data = data.get("order", {})
            payment_data = data.get("payment", {})
            webhook_type = webhook_data.get("type", "")
            
            order_id = order_data.get("order_id")
            cf_order_id = order_data.get("cf_order_id") or order_id
            
            # Get payment status from payment_data (NOT order_data)
            # Or derive from webhook type
            payment_status = payment_data.get("payment_status", "")
            
            # Map payment status or webhook type to our status
            if payment_status == "SUCCESS" or webhook_type == "PAYMENT_SUCCESS_WEBHOOK":
                status = PaymentStatus.SUCCESS
            elif payment_status == "FAILED" or webhook_type == "PAYMENT_FAILED_WEBHOOK":
                status = PaymentStatus.FAILED
            elif payment_status == "USER_DROPPED" or webhook_type == "PAYMENT_USER_DROPPED_WEBHOOK":
                status = PaymentStatus.CANCELLED
            else:
                status = self._map_status(payment_status or "PENDING")
            
            print(f"[DEBUG] Webhook parsed - order_id: {order_id}, payment_status: {payment_status}, webhook_type: {webhook_type}, mapped_status: {status}")
            
            return WebhookVerificationResult(
                is_valid=True,
                order_id=order_id,
                gateway_order_id=cf_order_id,
                gateway_payment_id=payment_data.get("cf_payment_id"),
                status=status,
                amount=order_data.get("order_amount"),
                payment_method=payment_data.get("payment_method", {}).get("type") if payment_data else None,
                raw_data=webhook_data
            )
            
        except Exception as e:
            return WebhookVerificationResult(
                is_valid=False,
                error_message=f"Webhook verification failed: {str(e)}"
            )
    
    async def initiate_refund(
        self,
        gateway_order_id: str,
        refund_amount: float,
        refund_id: str,
        reason: Optional[str] = None
    ) -> RefundResult:
        """Initiate a refund via Cashfree"""
        try:
            api_url = self.get_api_url(f"/orders/{gateway_order_id}/refunds")
            
            payload = {
                "refund_id": refund_id,
                "refund_amount": refund_amount,
            }
            
            if reason:
                payload["refund_note"] = reason
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    api_url,
                    headers=self._get_headers(),
                    json=payload
                )
                
                response_data = response.json()
                
                if response.status_code in [200, 201]:
                    return RefundResult(
                        success=True,
                        refund_id=refund_id,
                        gateway_refund_id=response_data.get("cf_refund_id"),
                        amount=response_data.get("refund_amount"),
                        status=response_data.get("refund_status"),
                        raw_response=response_data
                    )
                else:
                    error_msg = response_data.get("message", "Refund failed")
                    return RefundResult(
                        success=False,
                        refund_id=refund_id,
                        error_message=error_msg,
                        raw_response=response_data
                    )
                    
        except Exception as e:
            return RefundResult(
                success=False,
                refund_id=refund_id,
                error_message=str(e)
            )
