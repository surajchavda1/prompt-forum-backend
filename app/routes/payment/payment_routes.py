"""
Payment Routes
API endpoints for payment operations
"""
from fastapi import APIRouter, Depends, Query, Form, Request
from typing import Optional, Any
from datetime import datetime

from app.database import Database
from app.services.payment.payment_service import PaymentService
from app.routes.auth.dependencies import get_current_user
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/payments", tags=["Payments"])


def serialize_datetime(obj: Any) -> Any:
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    return obj


@router.get("/gateways")
async def get_available_gateways():
    """
    Get list of available payment gateways.
    Returns gateway info including fees and limits.
    """
    db = Database.get_db()
    payment_service = PaymentService(db)
    
    gateways = await payment_service.get_available_gateways()
    
    return success_response(
        message="Gateways retrieved successfully",
        data={"gateways": gateways}
    )


@router.get("/packages")
async def get_credit_packages():
    """
    Get available credit packages for purchase.
    Returns predefined credit packages with pricing.
    """
    db = Database.get_db()
    payment_service = PaymentService(db)
    
    packages = await payment_service.get_credit_packages()
    
    # Serialize datetime fields and return only necessary data
    safe_packages = []
    for pkg in packages:
        safe_packages.append({
            "package_id": pkg.get("package_id"),
            "name": pkg.get("name"),
            "description": pkg.get("description", ""),
            "price": pkg.get("price"),
            "credits": pkg.get("credits"),
            "bonus_credits": pkg.get("bonus_credits", 0),
            "total_credits": pkg.get("total_credits"),
            "currency": pkg.get("currency", "INR"),
            "discount_percentage": pkg.get("discount_percentage", 0),
            "original_price": pkg.get("original_price"),
            "is_popular": pkg.get("is_popular", False),
            "is_best_value": pkg.get("is_best_value", False),
            "badge": pkg.get("badge")
        })
    
    return success_response(
        message="Packages retrieved successfully",
        data={
            "packages": safe_packages,
            "currency": "INR"
        }
    )


@router.post("/create-order")
async def create_payment_order(
    request: Request,
    amount: float = Form(..., gt=0, description="Amount to pay (credits = amount, 1:1 ratio)"),
    gateway: str = Form("cashfree", description="Payment gateway to use"),
    package_id: Optional[str] = Form(None, description="Credit package ID (optional)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a payment order for credit purchase.
    
    Security:
    - Credits = Amount (1:1 ratio, no user input)
    - Email from logged-in user
    - Phone defaults to 9999999999
    - Return URL from gateway config (DB)
    
    Use package_id for predefined packages with bonus credits.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    payment_service = PaymentService(db)
    
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # SECURITY: Credits = Amount (1:1, no user manipulation)
    credits = amount
    
    # Build notify URL (webhook)
    base_url = str(request.base_url).rstrip("/")
    notify_url = f"{base_url}/api/payments/webhook/{gateway}"
    
    # SECURITY: Use logged-in user's email, default phone
    customer_email = current_user.get("email")
    customer_phone = "9999999999"  # Default for Cashfree
    
    success, message, order_data = await payment_service.create_payment_order(
        user_id=str(current_user["_id"]),
        amount=amount,
        credits=credits,
        gateway_id=gateway,
        package_id=package_id,
        customer_email=customer_email,
        customer_phone=customer_phone,
        customer_name=current_user.get("full_name") or current_user.get("username"),
        return_url=None,  # Will be fetched from gateway config
        notify_url=notify_url,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"order": order_data}
    )


@router.get("/order/{order_id}")
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get payment order details.
    Only the order owner can view.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    payment_service = PaymentService(db)
    
    order = await payment_service.get_order(order_id)
    
    if not order:
        return error_response(message="Order not found", status_code=404)
    
    # Security: only owner can view
    if order["user_id"] != str(current_user["_id"]):
        return error_response(message="Access denied", status_code=403)
    
    # Return safe order data with serialized datetimes
    return success_response(
        message="Order retrieved successfully",
        data={
            "order": {
                "order_id": order["order_id"],
                "amount": order["amount"],
                "credits": order["credits"],
                "total_amount": order["total_amount"],
                "currency": order["currency"],
                "gateway": order["gateway"],
                "status": order["status"],
                "payment_link": order.get("payment_link"),
                "created_at": serialize_datetime(order.get("created_at")),
                "paid_at": serialize_datetime(order.get("paid_at")),
                "expires_at": serialize_datetime(order.get("expires_at"))
            }
        }
    )


@router.get("/order/{order_id}/status")
async def get_order_status(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get payment order status.
    Polls the gateway if order is pending.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    payment_service = PaymentService(db)
    
    # Verify ownership first
    order = await payment_service.get_order(order_id)
    if not order:
        return error_response(message="Order not found", status_code=404)
    
    if order["user_id"] != str(current_user["_id"]):
        return error_response(message="Access denied", status_code=403)
    
    success, message, status_data = await payment_service.get_order_status(order_id)
    
    if not success:
        return error_response(message=message, status_code=400)
    
    # Serialize datetime objects
    serialized_status = serialize_datetime(status_data)
    
    return success_response(
        message=message,
        data={"status": serialized_status}
    )


@router.get("/orders")
async def get_user_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's payment order history.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    payment_service = PaymentService(db)
    
    orders, pagination = await payment_service.get_user_orders(
        user_id=str(current_user["_id"]),
        page=page,
        limit=limit,
        status=status
    )
    
    # Return safe order data with serialized datetimes
    safe_orders = []
    for order in orders:
        safe_orders.append({
            "order_id": order["order_id"],
            "amount": order["amount"],
            "credits": order["credits"],
            "total_amount": order["total_amount"],
            "currency": order["currency"],
            "gateway": order["gateway"],
            "status": order["status"],
            "package_name": order.get("package_name"),
            "created_at": serialize_datetime(order.get("created_at")),
            "paid_at": serialize_datetime(order.get("paid_at"))
        })
    
    return success_response(
        message="Orders retrieved successfully",
        data={
            "orders": safe_orders,
            "pagination": pagination
        }
    )
