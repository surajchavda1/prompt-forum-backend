"""
Withdrawal Routes - Fully Dynamic
All methods and settings from database
"""
from fastapi import APIRouter, Depends, Query, Request, Body
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum

from app.database import Database
from app.services.payment.withdrawal_service import WithdrawalService
from app.routes.auth.dependencies import get_current_user
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/withdrawals", tags=["Withdrawals"])


def serialize_datetime(obj: Any) -> Any:
    """Convert datetime objects to ISO format strings"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    elif isinstance(obj, Enum):
        return obj.value
    return obj


# ==================== REQUEST MODELS ====================

class WithdrawalRequest(BaseModel):
    """Generic withdrawal request - payment details vary by method"""
    amount: float = Field(..., gt=0, description="Amount in credits to withdraw")
    method_id: str = Field(..., description="Withdrawal method ID from /methods")
    currency: str = Field("USD", description="Target currency")
    payment_details: Dict[str, Any] = Field(..., description="Method-specific payment details")
    notes: Optional[str] = None


# ==================== ROUTES ====================

@router.get("/config")
async def get_withdrawal_config():
    """
    Get withdrawal configuration.
    All settings from database - fully dynamic.
    """
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    config = await withdrawal_service.get_config()
    
    return success_response(
        message="Withdrawal configuration retrieved",
        data={"config": config}
    )


@router.get("/methods")
async def get_withdrawal_methods(
    currency: Optional[str] = Query(None, description="Filter by currency")
):
    """
    Get available withdrawal methods.
    Methods are configured in database - fully dynamic.
    """
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    methods = await withdrawal_service.get_available_methods(currency)
    
    return success_response(
        message="Withdrawal methods retrieved",
        data={"methods": methods}
    )


@router.get("/limits")
async def get_withdrawal_limits(current_user: dict = Depends(get_current_user)):
    """
    Get user's withdrawal limits and current usage.
    All limits from database configuration.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    limits = await withdrawal_service.get_withdrawal_limits(str(current_user["_id"]))
    
    return success_response(
        message="Withdrawal limits retrieved",
        data={"limits": limits}
    )


@router.get("/calculate-fees")
async def calculate_withdrawal_fees(
    amount: float = Query(..., gt=0, description="Amount to withdraw"),
    method_id: str = Query(..., description="Withdrawal method ID"),
    currency: str = Query("USD", description="Target currency"),
    current_user: dict = Depends(get_current_user)
):
    """
    Calculate withdrawal fees before submitting request.
    Fees are calculated dynamically from database config.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    fees = await withdrawal_service.calculate_fees(
        amount=amount,
        method_id=method_id,
        currency=currency
    )
    
    return success_response(
        message="Fees calculated",
        data={"fees": fees.dict()}
    )


@router.post("/request")
async def create_withdrawal_request(
    request: Request,
    data: WithdrawalRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a withdrawal request.
    
    Payment details format depends on the method:
    
    Bank Transfer:
    {
        "account_holder_name": "John Doe",
        "bank_name": "Bank of America",
        "account_number": "123456789",
        "routing_number": "026009593",  // US
        "swift_code": "BOFAUS3N",        // International
        "iban": "...",                    // SEPA
        "ifsc_code": "...",               // India
        "country": "US"
    }
    
    PayPal/Wise:
    {
        "email": "user@example.com",
        "account_holder_name": "John Doe"
    }
    
    Crypto:
    {
        "wallet_address": "0x...",
        "network": "ERC20",
        "memo_tag": "..."  // Optional
    }
    
    UPI (India):
    {
        "upi_id": "name@upi",
        "account_holder_name": "Name"
    }
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    success, message, withdrawal_data = await withdrawal_service.create_withdrawal_request(
        user_id=str(current_user["_id"]),
        amount=data.amount,
        method_id=data.method_id,
        payment_details=data.payment_details,
        currency=data.currency,
        user_notes=data.notes,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"withdrawal": serialize_datetime(withdrawal_data)}
    )


@router.post("/{withdrawal_id}/cancel")
async def cancel_withdrawal(
    withdrawal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a pending withdrawal request.
    Only withdrawals in PENDING status can be cancelled.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    success, message = await withdrawal_service.cancel_withdrawal(
        user_id=str(current_user["_id"]),
        withdrawal_id=withdrawal_id
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(message=message)


@router.get("/{withdrawal_id}")
async def get_withdrawal(
    withdrawal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get withdrawal details"""
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    withdrawal = await withdrawal_service.get_withdrawal(withdrawal_id)
    
    if not withdrawal:
        return error_response(message="Withdrawal not found", status_code=404)
    
    # Security: only owner can view
    if withdrawal["user_id"] != str(current_user["_id"]):
        return error_response(message="Access denied", status_code=403)
    
    return success_response(
        message="Withdrawal retrieved",
        data={"withdrawal": serialize_datetime(withdrawal)}
    )


@router.get("")
async def get_user_withdrawals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """Get user's withdrawal history"""
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    withdrawal_service = WithdrawalService(db)
    
    withdrawals, pagination = await withdrawal_service.get_user_withdrawals(
        user_id=str(current_user["_id"]),
        page=page,
        limit=limit,
        status=status
    )
    
    return success_response(
        message="Withdrawals retrieved",
        data={
            "withdrawals": serialize_datetime(withdrawals),
            "pagination": pagination
        }
    )
