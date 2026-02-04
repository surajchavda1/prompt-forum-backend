"""
Payment Gateway Factory
Creates and manages payment gateway instances
"""
from typing import Dict, Any, Optional, Type
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.payment.gateways.base import BasePaymentGateway
from app.services.payment.gateways.cashfree import CashfreeGateway


class PaymentGatewayFactory:
    """
    Factory for creating payment gateway instances.
    Supports dynamic gateway registration and configuration.
    """
    
    # Registry of available gateways
    _gateways: Dict[str, Type[BasePaymentGateway]] = {
        "cashfree": CashfreeGateway,
        # Add more gateways here:
        # "razorpay": RazorpayGateway,
        # "stripe": StripeGateway,
        # "paypal": PaypalGateway,
    }
    
    # Cached gateway instances
    _instances: Dict[str, BasePaymentGateway] = {}
    
    @classmethod
    def register_gateway(cls, gateway_id: str, gateway_class: Type[BasePaymentGateway]):
        """
        Register a new payment gateway.
        
        Args:
            gateway_id: Unique identifier for the gateway
            gateway_class: Gateway class implementing BasePaymentGateway
        """
        cls._gateways[gateway_id] = gateway_class
    
    @classmethod
    def get_available_gateways(cls) -> list:
        """Get list of available gateway IDs"""
        return list(cls._gateways.keys())
    
    @classmethod
    def get_gateway(
        cls,
        gateway_id: str,
        config: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> BasePaymentGateway:
        """
        Get a payment gateway instance.
        
        Args:
            gateway_id: Gateway identifier (e.g., "cashfree")
            config: Optional configuration override
            use_cache: Whether to use cached instance
            
        Returns:
            Payment gateway instance
            
        Raises:
            ValueError: If gateway is not registered
        """
        if gateway_id not in cls._gateways:
            raise ValueError(f"Unknown payment gateway: {gateway_id}. Available: {list(cls._gateways.keys())}")
        
        cache_key = f"{gateway_id}_{hash(str(config)) if config else 'default'}"
        
        # Return cached instance if available
        if use_cache and cache_key in cls._instances:
            return cls._instances[cache_key]
        
        # Create new instance
        gateway_class = cls._gateways[gateway_id]
        instance = gateway_class(config)
        
        # Cache instance
        if use_cache:
            cls._instances[cache_key] = instance
        
        return instance
    
    @classmethod
    async def get_gateway_from_db(
        cls,
        db: AsyncIOMotorDatabase,
        gateway_id: str
    ) -> Optional[BasePaymentGateway]:
        """
        Get gateway with configuration from database.
        
        Args:
            db: Database instance
            gateway_id: Gateway identifier
            
        Returns:
            Configured gateway instance or None
        """
        # Get gateway config from database
        gateway_config = await db.payment_gateway_configs.find_one({
            "gateway_id": gateway_id,
            "status": "active"
        })
        
        if not gateway_config:
            # Fall back to environment config (don't use cache to get fresh env vars)
            return cls.get_gateway(gateway_id, use_cache=False)
        
        # Build config from database (credentials always come from env)
        config = {
            "is_sandbox": gateway_config.get("is_sandbox", True),
            "platform_fee_percentage": gateway_config.get("platform_fee_percentage", 0),
            "platform_fee_fixed": gateway_config.get("platform_fee_fixed", 0),
            "gateway_fee_percentage": gateway_config.get("gateway_fee_percentage", 0),
            "gateway_fee_fixed": gateway_config.get("gateway_fee_fixed", 0),
            "min_amount": gateway_config.get("min_amount", 1),
            "max_amount": gateway_config.get("max_amount", 100000),
        }
        
        # Don't use cache to ensure fresh credentials from env
        return cls.get_gateway(gateway_id, config, use_cache=False)
    
    @classmethod
    async def get_default_gateway(
        cls,
        db: Optional[AsyncIOMotorDatabase] = None
    ) -> BasePaymentGateway:
        """
        Get the default payment gateway.
        
        Args:
            db: Optional database for config lookup
            
        Returns:
            Default gateway instance
        """
        if db:
            # Try to get default from database
            default_config = await db.payment_gateway_configs.find_one({
                "is_default": True,
                "status": "active"
            })
            
            if default_config:
                return await cls.get_gateway_from_db(db, default_config["gateway_id"])
        
        # Fall back to Cashfree as default
        return cls.get_gateway("cashfree")
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached gateway instances"""
        cls._instances.clear()


# Convenience function
def get_payment_gateway(
    gateway_id: str = "cashfree",
    config: Optional[Dict[str, Any]] = None
) -> BasePaymentGateway:
    """
    Get a payment gateway instance.
    
    Args:
        gateway_id: Gateway identifier
        config: Optional configuration
        
    Returns:
        Payment gateway instance
    """
    return PaymentGatewayFactory.get_gateway(gateway_id, config)
