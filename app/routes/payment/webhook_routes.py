"""
Payment Webhook Routes
Endpoints for payment gateway webhooks
SECURITY: These endpoints verify signatures before processing
"""
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.database import Database
from app.services.payment.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payment Webhooks"])


@router.post("/webhook/{gateway}")
async def handle_payment_webhook(
    gateway: str,
    request: Request
):
    """
    Handle payment webhook from any gateway.
    
    SECURITY:
    - Verifies webhook signature
    - Processes idempotently (duplicate webhooks safe)
    - Returns 200 even on errors (to prevent retries for invalid webhooks)
    """
    try:
        # Get raw body for signature verification
        raw_body = await request.body()
        headers = dict(request.headers)
        
        db = Database.get_db()
        payment_service = PaymentService(db)
        
        # Process webhook
        success, message = await payment_service.process_webhook(
            gateway_id=gateway,
            headers=headers,
            raw_body=raw_body
        )
        
        if success:
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": message}
            )
        else:
            # Log failed webhooks but return 200 to prevent retries
            print(f"[WARN] Webhook processing failed: {message}")
            return JSONResponse(
                status_code=200,
                content={"status": "failed", "message": message}
            )
            
    except Exception as e:
        print(f"[ERROR] Webhook handler error: {str(e)}")
        # Return 200 to prevent gateway retries
        return JSONResponse(
            status_code=200,
            content={"status": "error", "message": "Internal error"}
        )


@router.post("/webhook/cashfree")
async def handle_cashfree_webhook(request: Request):
    """
    Handle Cashfree payment webhook.
    Alias for /webhook/{gateway} with gateway=cashfree.
    """
    return await handle_payment_webhook("cashfree", request)


# Health check for webhook endpoint
@router.get("/webhook/health")
async def webhook_health():
    """
    Health check for webhook endpoint.
    Can be used to verify webhook URL is accessible.
    """
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "message": "Webhook endpoint healthy"}
    )
