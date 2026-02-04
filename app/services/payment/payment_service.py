"""
Payment Service
Orchestrates payment operations across gateways
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.services.payment.gateways.factory import PaymentGatewayFactory
from app.services.payment.gateways.base import PaymentStatus
from app.services.payment.wallet_service import WalletService
from app.models.payment.payment_order import PaymentOrderStatus, PaymentOrderInDB
from app.models.payment.transaction import TransactionCategory


class PaymentService:
    """
    Service for payment operations.
    Handles payment order creation, status tracking, and webhook processing.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.orders = db.payment_orders
        self.packages = db.credit_packages
        self.gateway_configs = db.payment_gateway_configs
        self.wallet_service = WalletService(db)
    
    @staticmethod
    def generate_order_id() -> str:
        """Generate unique order ID"""
        return f"ORD_{uuid.uuid4().hex[:12].upper()}"
    
    async def get_credit_packages(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get available credit packages"""
        query = {"status": "active"} if active_only else {}
        
        cursor = self.packages.find(query).sort("sort_order", 1)
        packages = await cursor.to_list(length=100)
        
        # Convert ObjectId to string
        for pkg in packages:
            if "_id" in pkg:
                pkg["_id"] = str(pkg["_id"])
        
        return packages
    
    async def get_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific credit package"""
        return await self.packages.find_one({"package_id": package_id, "status": "active"})
    
    async def get_available_gateways(self) -> List[Dict[str, Any]]:
        """Get list of available payment gateways"""
        cursor = self.gateway_configs.find({"status": "active"})
        configs = await cursor.to_list(length=50)
        
        # Return public info only
        gateways = []
        for config in configs:
            gateways.append({
                "gateway_id": config["gateway_id"],
                "name": config.get("name", config["gateway_id"]),
                "description": config.get("description", ""),
                "is_default": config.get("is_default", False),
                "min_amount": config.get("min_amount", 1),
                "max_amount": config.get("max_amount", 100000),
                "platform_fee_percentage": config.get("platform_fee_percentage", 0),
                "platform_fee_fixed": config.get("platform_fee_fixed", 0),
            })
        
        # If no configs in DB, return default
        if not gateways:
            gateways = [{
                "gateway_id": "cashfree",
                "name": "Cashfree Payments",
                "description": "Pay via UPI, Cards, Net Banking",
                "is_default": True,
                "min_amount": 1,
                "max_amount": 100000,
                "platform_fee_percentage": 0,
                "platform_fee_fixed": 0,
            }]
        
        return gateways
    
    async def create_payment_order(
        self,
        user_id: str,
        amount: float,
        credits: float,
        gateway_id: str = "cashfree",
        package_id: Optional[str] = None,
        customer_email: str = None,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        return_url: Optional[str] = None,
        notify_url: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Create a payment order.
        
        Args:
            user_id: User's ID
            amount: Amount to pay
            credits: Credits to receive
            gateway_id: Payment gateway to use
            package_id: Optional credit package ID
            customer_email: User's email
            ...
            
        Returns:
            (success, message, order_data)
        """
        try:
            # Get gateway config from DB first (for return_url and other settings)
            gateway_config = await self.gateway_configs.find_one({"gateway_id": gateway_id, "status": "active"})
            
            # Get gateway instance
            gateway = await PaymentGatewayFactory.get_gateway_from_db(self.db, gateway_id)
            if not gateway:
                gateway = PaymentGatewayFactory.get_gateway(gateway_id)
            
            # Calculate fees
            platform_fee, gateway_fee, total_amount = gateway.calculate_fees(amount)
            
            # Get return_url from DB config if not provided
            if not return_url and gateway_config:
                return_url = gateway_config.get("return_url")
            
            # Generate order ID
            order_id = self.generate_order_id()
            
            # Get package info if provided
            package_name = None
            if package_id:
                package = await self.get_package(package_id)
                if package:
                    package_name = package.get("name")
                    # Override with package values
                    amount = package.get("price", amount)
                    credits = package.get("total_credits", credits)
                    platform_fee, gateway_fee, total_amount = gateway.calculate_fees(amount)
            
            # Create order in gateway
            result = await gateway.create_order(
                order_id=order_id,
                amount=total_amount,
                currency="INR",
                customer_id=user_id,
                customer_email=customer_email,
                customer_phone=customer_phone,
                customer_name=customer_name,
                return_url=return_url,
                notify_url=notify_url,
                metadata={"user_id": user_id, "credits": credits, **(metadata or {})}
            )
            
            if not result.success:
                return False, result.error_message or "Failed to create payment order", None
            
            # Save order to database
            now = datetime.utcnow()
            order_doc = {
                "order_id": order_id,
                "user_id": user_id,
                "amount": amount,
                "credits": credits,
                "fee": platform_fee,
                "gateway_fee": gateway_fee,
                "total_amount": total_amount,
                "currency": "INR",
                "package_id": package_id,
                "package_name": package_name,
                "gateway": gateway_id,
                "gateway_order_id": result.gateway_order_id,
                "gateway_response": result.raw_response or {},
                "payment_link": result.payment_link,
                "payment_session_id": result.payment_session_id,
                "status": PaymentOrderStatus.CREATED,
                "created_at": now,
                "updated_at": now,
                "expires_at": now + timedelta(hours=1),  # 1 hour expiry
                "ip_address": ip_address,
                "user_agent": user_agent,
                "metadata": metadata or {}
            }
            
            await self.orders.insert_one(order_doc)
            
            # Return order data
            # Determine environment for SDK
            is_sandbox = gateway.is_sandbox if hasattr(gateway, 'is_sandbox') else True
            
            order_data = {
                "order_id": order_id,
                "amount": amount,
                "credits": credits,
                "total_amount": total_amount,
                "currency": "INR",
                "gateway": gateway_id,
                "payment_session_id": result.payment_session_id,
                "status": "created",
                "expires_at": order_doc["expires_at"].isoformat(),
                # SDK integration info
                "sdk_mode": "sandbox" if is_sandbox else "production",
                "sdk_url": "https://sdk.cashfree.com/js/v3/cashfree.js",
                "integration_note": "Use Cashfree JS SDK with payment_session_id to open checkout"
            }
            
            return True, "Payment order created successfully", order_data
            
        except Exception as e:
            print(f"[ERROR] create_payment_order failed: {str(e)}")
            return False, f"Failed to create payment order: {str(e)}", None
    
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get payment order by ID"""
        order = await self.orders.find_one({"order_id": order_id})
        if order and "_id" in order:
            order["_id"] = str(order["_id"])
        return order
    
    async def get_order_status(self, order_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Get payment order status (polls gateway if pending).
        
        Returns:
            (success, message, status_data)
        """
        order = await self.get_order(order_id)
        if not order:
            return False, "Order not found", None
        
        # If already in final state, return cached status
        if order["status"] in [PaymentOrderStatus.PAID, PaymentOrderStatus.FAILED, 
                               PaymentOrderStatus.EXPIRED, PaymentOrderStatus.REFUNDED]:
            return True, "Order status retrieved", {
                "order_id": order_id,
                "status": order["status"],
                "credits": order.get("credits"),
                "paid_at": order.get("paid_at")
            }
        
        # Poll gateway for status
        gateway = PaymentGatewayFactory.get_gateway(order["gateway"])
        result = await gateway.get_order_status(order.get("gateway_order_id") or order_id)
        
        if result.success:
            # Update order if status changed
            new_status = self._map_gateway_status(result.status)
            
            if new_status != order["status"]:
                update_data = {
                    "status": new_status,
                    "updated_at": datetime.utcnow()
                }
                
                if new_status == PaymentOrderStatus.PAID:
                    update_data["paid_at"] = datetime.utcnow()
                    update_data["gateway_payment_id"] = result.gateway_payment_id
                    
                    # Credit wallet
                    await self._credit_wallet_for_order(order)
                
                await self.orders.update_one(
                    {"order_id": order_id},
                    {"$set": update_data}
                )
            
            return True, "Order status retrieved", {
                "order_id": order_id,
                "status": new_status,
                "credits": order.get("credits"),
                "gateway_status": result.status.value
            }
        
        return True, "Order status retrieved", {
            "order_id": order_id,
            "status": order["status"],
            "credits": order.get("credits")
        }
    
    async def process_webhook(
        self,
        gateway_id: str,
        headers: Dict[str, str],
        raw_body: bytes
    ) -> Tuple[bool, str]:
        """
        Process payment webhook from gateway.
        
        Args:
            gateway_id: Gateway identifier
            headers: Request headers
            raw_body: Raw request body
            
        Returns:
            (success, message)
        """
        try:
            gateway = PaymentGatewayFactory.get_gateway(gateway_id)
            
            # Verify webhook signature
            result = await gateway.verify_webhook(headers, raw_body)
            
            if not result.is_valid:
                print(f"[SECURITY] Invalid webhook signature: {result.error_message}")
                return False, result.error_message or "Invalid webhook signature"
            
            # Get order
            order = await self.get_order(result.order_id)
            if not order:
                print(f"[WARN] Webhook for unknown order: {result.order_id}")
                return True, "Order not found (may be processed already)"
            
            # Skip if already processed
            if order["status"] == PaymentOrderStatus.PAID:
                return True, "Order already processed"
            
            # Process based on status
            new_status = self._map_gateway_status(result.status)
            
            update_data = {
                "status": new_status,
                "updated_at": datetime.utcnow(),
                "webhook_received_at": datetime.utcnow(),
                "gateway_payment_id": result.gateway_payment_id
            }
            
            if new_status == PaymentOrderStatus.PAID:
                update_data["paid_at"] = datetime.utcnow()
                update_data["credits_credited"] = False  # Will be set to True after crediting
                
                # Update order first
                await self.orders.update_one(
                    {"order_id": result.order_id},
                    {"$set": update_data}
                )
                
                # Credit wallet (idempotent via idempotency_key)
                credit_success = await self._credit_wallet_for_order(order)
                
                # Mark credits as credited
                if credit_success:
                    await self.orders.update_one(
                        {"order_id": result.order_id},
                        {"$set": {"credits_credited": True, "credited_at": datetime.utcnow()}}
                    )
                
                return True, "Payment processed successfully"
            
            elif new_status in [PaymentOrderStatus.FAILED, PaymentOrderStatus.EXPIRED]:
                await self.orders.update_one(
                    {"order_id": result.order_id},
                    {"$set": update_data}
                )
                return True, f"Payment {new_status}"
            
            # Update status
            await self.orders.update_one(
                {"order_id": result.order_id},
                {"$set": update_data}
            )
            
            return True, "Webhook processed"
            
        except Exception as e:
            print(f"[ERROR] process_webhook failed: {str(e)}")
            return False, f"Webhook processing failed: {str(e)}"
    
    async def _credit_wallet_for_order(self, order: Dict[str, Any]) -> bool:
        """Credit user's wallet for a paid order"""
        try:
            print(f"[INFO] Crediting wallet for order {order['order_id']}")
            print(f"[INFO] User: {order['user_id']}, Credits: {order['credits']}")
            
            success, message, transaction = await self.wallet_service.credit_wallet(
                user_id=order["user_id"],
                amount=order["credits"],
                category=TransactionCategory.TOPUP,
                description=f"Credit purchase - {order.get('package_name') or 'Custom amount'}",
                reference_type="payment_order",
                reference_id=order["order_id"],
                gateway=order["gateway"],
                gateway_order_id=order.get("gateway_order_id"),
                idempotency_key=f"CREDIT_{order['order_id']}"
            )
            
            if success:
                print(f"[OK] Credited {order['credits']} credits to user {order['user_id']} for order {order['order_id']}")
                if transaction:
                    print(f"[OK] Transaction ID: {transaction.get('transaction_id')}")
            else:
                print(f"[ERROR] Failed to credit wallet: {message}")
            
            return success
            
        except Exception as e:
            import traceback
            print(f"[ERROR] _credit_wallet_for_order failed: {str(e)}")
            traceback.print_exc()
            return False
    
    def _map_gateway_status(self, status: PaymentStatus) -> PaymentOrderStatus:
        """Map gateway status to order status"""
        mapping = {
            PaymentStatus.CREATED: PaymentOrderStatus.CREATED,
            PaymentStatus.PENDING: PaymentOrderStatus.PENDING,
            PaymentStatus.SUCCESS: PaymentOrderStatus.PAID,
            PaymentStatus.FAILED: PaymentOrderStatus.FAILED,
            PaymentStatus.EXPIRED: PaymentOrderStatus.EXPIRED,
            PaymentStatus.CANCELLED: PaymentOrderStatus.CANCELLED,
            PaymentStatus.REFUNDED: PaymentOrderStatus.REFUNDED,
        }
        return mapping.get(status, PaymentOrderStatus.PENDING)
    
    async def get_user_orders(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """Get user's payment order history"""
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        
        skip = (page - 1) * limit
        
        total = await self.orders.count_documents(query)
        cursor = self.orders.find(query).sort("created_at", -1).skip(skip).limit(limit)
        orders = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for order in orders:
            if "_id" in order:
                order["_id"] = str(order["_id"])
        
        pagination = {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
        
        return orders, pagination
    
    async def initiate_refund(
        self,
        order_id: str,
        amount: Optional[float] = None,
        reason: str = ""
    ) -> Tuple[bool, str]:
        """Initiate refund for an order"""
        order = await self.get_order(order_id)
        if not order:
            return False, "Order not found"
        
        if order["status"] != PaymentOrderStatus.PAID:
            return False, "Can only refund paid orders"
        
        refund_amount = amount or order["total_amount"]
        refund_id = f"REF_{uuid.uuid4().hex[:12].upper()}"
        
        gateway = PaymentGatewayFactory.get_gateway(order["gateway"])
        result = await gateway.initiate_refund(
            gateway_order_id=order.get("gateway_order_id") or order_id,
            refund_amount=refund_amount,
            refund_id=refund_id,
            reason=reason
        )
        
        if result.success:
            # Debit credits from wallet
            await self.wallet_service.debit_wallet(
                user_id=order["user_id"],
                amount=order["credits"],
                category=TransactionCategory.REFUND,
                description=f"Refund for order {order_id}",
                reference_type="payment_order",
                reference_id=order_id
            )
            
            # Update order status
            await self.orders.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": PaymentOrderStatus.REFUNDED,
                    "refund_id": refund_id,
                    "refund_amount": refund_amount,
                    "refunded_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }}
            )
            
            return True, "Refund initiated successfully"
        
        return False, result.error_message or "Refund failed"
