"""
Wallet Routes
API endpoints for wallet operations
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, Any
from datetime import datetime

from app.database import Database
from app.services.payment.wallet_service import WalletService
from app.routes.auth.dependencies import get_current_user
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/wallet", tags=["Wallet"])


def serialize_datetime(obj: Any) -> Any:
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    return obj


@router.get("/debug-auth")
async def debug_auth(current_user: dict = Depends(get_current_user)):
    """
    Debug endpoint to test authentication.
    Returns user info if authenticated.
    """
    if not current_user:
        return error_response(
            message="Authentication failed. Token may be missing, invalid, or expired.",
            status_code=401
        )
    
    return success_response(
        message="Authentication successful",
        data={
            "user_id": str(current_user["_id"]),
            "email": current_user.get("email"),
            "username": current_user.get("username"),
            "is_active": current_user.get("is_active")
        }
    )


@router.get("")
async def get_wallet(current_user: dict = Depends(get_current_user)):
    """
    Get current user's wallet.
    Returns balance, locked balance, and available balance.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    wallet_service = WalletService(db)
    
    wallet = await wallet_service.get_wallet(str(current_user["_id"]))
    
    if not wallet:
        return error_response(message="Wallet not found", status_code=404)
    
    return success_response(
        message="Wallet retrieved successfully",
        data={
            "wallet": {
                "user_id": wallet.get("user_id"),
                "balance": wallet.get("balance", 0.0),
                "locked_balance": wallet.get("locked_balance", 0.0),
                "available_balance": wallet.get("available_balance", 0.0),
                "currency": wallet.get("currency", "INR"),
                "status": wallet.get("status", "active"),
                "total_credited": wallet.get("total_credited", 0.0),
                "total_debited": wallet.get("total_debited", 0.0)
            }
        }
    )


@router.get("/balance")
async def get_balance(current_user: dict = Depends(get_current_user)):
    """
    Get current user's balance summary.
    Quick endpoint for just balance info.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    wallet_service = WalletService(db)
    
    balance_info = await wallet_service.get_balance(str(current_user["_id"]))
    
    return success_response(
        message="Balance retrieved successfully",
        data=balance_info
    )


@router.get("/transactions")
async def get_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by transaction type"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's transaction history.
    
    Categories: topup, contest_entry, contest_create, contest_prize, withdrawal, bonus, refund
    Types: credit, debit, refund, lock, unlock
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    wallet_service = WalletService(db)
    
    transactions, pagination = await wallet_service.get_transaction_history(
        user_id=str(current_user["_id"]),
        page=page,
        limit=limit,
        category=category,
        transaction_type=type
    )
    
    # Serialize datetime fields in transactions
    serialized_transactions = serialize_datetime(transactions)
    
    return success_response(
        message="Transactions retrieved successfully",
        data={
            "transactions": serialized_transactions,
            "pagination": pagination
        }
    )


@router.get("/stats")
async def get_wallet_stats(current_user: dict = Depends(get_current_user)):
    """
    Get detailed wallet statistics.
    Includes breakdown by transaction category.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    wallet_service = WalletService(db)
    
    stats = await wallet_service.get_wallet_stats(str(current_user["_id"]))
    
    return success_response(
        message="Wallet stats retrieved successfully",
        data={"stats": stats}
    )


@router.get("/check-balance")
async def check_balance(
    amount: float = Query(..., gt=0, description="Amount to check"),
    current_user: dict = Depends(get_current_user)
):
    """
    Check if user has sufficient balance for an amount.
    Useful before initiating transactions.
    """
    if not current_user:
        return error_response(message="Authentication required", status_code=401)
    
    db = Database.get_db()
    wallet_service = WalletService(db)
    
    has_sufficient, available = await wallet_service.check_balance(
        str(current_user["_id"]),
        amount
    )
    
    return success_response(
        message="Balance check completed",
        data={
            "required_amount": amount,
            "available_balance": available,
            "has_sufficient_balance": has_sufficient
        }
    )
