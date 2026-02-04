"""
Seed Withdrawal Configuration and Methods
Creates dynamic withdrawal settings in database.
Run: python seed_withdrawal.py
"""
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "promptforum")


# ==================== GLOBAL CONFIGURATION ====================
WITHDRAWAL_CONFIG = {
    "config_id": "global",
    
    # Global Limits (in credits)
    "min_withdrawal_amount": 100,
    "max_withdrawal_amount": 100000,
    "daily_withdrawal_limit": 50000,
    "monthly_withdrawal_limit": 500000,
    "max_pending_requests": 3,
    
    # Platform Fees
    "platform_fee_percentage": 5.0,      # 5% platform fee
    "platform_fee_fixed": 0.0,           # No fixed platform fee
    "platform_fee_min": 10.0,            # Minimum 10 credits fee
    "platform_fee_max": 500.0,           # Maximum 500 credits fee
    
    # Exchange Rates (1 credit = X currency)
    "credit_to_usd_rate": 1.0,
    "credit_to_inr_rate": 83.0,
    "credit_to_eur_rate": 0.92,
    "credit_to_gbp_rate": 0.79,
    "credit_to_usdt_rate": 1.0,
    "credit_to_usdc_rate": 1.0,
    
    # Security Settings
    "cooldown_hours": 24,                # 24 hours between withdrawals
    "require_kyc": False,                # KYC not required by default
    "require_2fa": False,                # 2FA not required by default
    "require_email_verification": True,  # Email verification required
    "min_account_age_days": 0,           # No minimum account age
    "min_successful_payments": 0,        # No minimum payments required
    
    # Processing Settings
    "auto_approve_threshold": 0.0,       # 0 = no auto-approve
    "default_processing_days": 3,
    
    # Supported Currencies
    "supported_currencies": ["USD", "EUR", "GBP", "INR", "USDT", "USDC"],
    "default_currency": "USD",
    
    # Feature Flags
    "withdrawals_enabled": True,
    "new_user_withdrawals_enabled": True,
    "maintenance_mode": False,
    "maintenance_message": "",
    
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}


# ==================== WITHDRAWAL METHODS ====================
WITHDRAWAL_METHODS = [
    # Bank Transfers
    {
        "method_id": "bank_transfer_international",
        "name": "International Bank Transfer (SWIFT)",
        "description": "Wire transfer to any bank worldwide via SWIFT",
        "is_active": True,
        "supported_currencies": ["USD", "EUR", "GBP", "INR"],
        "supported_countries": [],  # Empty = all countries
        "fee_type": "fixed",
        "fee_fixed": 25.0,
        "fee_percentage": 0.0,
        "fee_min": 25.0,
        "fee_max": 0,            # 0 = no cap
        "min_amount": 100,
        "max_amount": 100000,
        "processing_days": 5,
        "requires_verification": True,
        "icon": "bank",
        "sort_order": 1,
        "metadata": {
            "required_fields": ["account_holder_name", "bank_name", "account_number", "swift_code", "country"],
            "optional_fields": ["routing_number", "iban", "address"]
        }
    },
    {
        "method_id": "bank_transfer_ach",
        "name": "ACH Transfer (US Only)",
        "description": "Free domestic bank transfer within USA",
        "is_active": True,
        "supported_currencies": ["USD"],
        "supported_countries": ["US"],
        "fee_type": "fixed",
        "fee_fixed": 0.0,
        "fee_percentage": 0.0,
        "fee_min": 0,
        "fee_max": 0,
        "min_amount": 10,
        "max_amount": 50000,
        "processing_days": 3,
        "requires_verification": False,
        "icon": "bank",
        "sort_order": 2,
        "metadata": {
            "required_fields": ["account_holder_name", "bank_name", "account_number", "routing_number"],
            "optional_fields": []
        }
    },
    {
        "method_id": "bank_transfer_sepa",
        "name": "SEPA Transfer (EU)",
        "description": "Low-cost bank transfer within EU/EEA",
        "is_active": True,
        "supported_currencies": ["EUR"],
        "supported_countries": ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"],
        "fee_type": "fixed",
        "fee_fixed": 1.0,
        "fee_percentage": 0.0,
        "fee_min": 1.0,
        "fee_max": 0,
        "min_amount": 10,
        "max_amount": 100000,
        "processing_days": 2,
        "requires_verification": False,
        "icon": "bank",
        "sort_order": 3,
        "metadata": {
            "required_fields": ["account_holder_name", "iban", "bic"],
            "optional_fields": []
        }
    },
    
    # India-specific
    {
        "method_id": "upi",
        "name": "UPI Transfer",
        "description": "Instant transfer via UPI (India)",
        "is_active": True,
        "supported_currencies": ["INR"],
        "supported_countries": ["IN"],
        "fee_type": "fixed",
        "fee_fixed": 0.0,
        "fee_percentage": 0.0,
        "fee_min": 0,
        "fee_max": 0,
        "min_amount": 100,       # ~$1.20
        "max_amount": 100000,    # UPI limit
        "processing_days": 1,
        "requires_verification": False,
        "icon": "upi",
        "sort_order": 4,
        "metadata": {
            "required_fields": ["upi_id", "account_holder_name"],
            "optional_fields": []
        }
    },
    {
        "method_id": "bank_transfer_india",
        "name": "Bank Transfer (India - IMPS/NEFT)",
        "description": "Indian bank transfer via IMPS or NEFT",
        "is_active": True,
        "supported_currencies": ["INR"],
        "supported_countries": ["IN"],
        "fee_type": "fixed",
        "fee_fixed": 5.0,
        "fee_percentage": 0.0,
        "fee_min": 5.0,
        "fee_max": 0,
        "min_amount": 100,
        "max_amount": 500000,
        "processing_days": 1,
        "requires_verification": False,
        "icon": "bank",
        "sort_order": 5,
        "metadata": {
            "required_fields": ["account_holder_name", "bank_name", "account_number", "ifsc_code"],
            "optional_fields": []
        }
    },
    
    # Digital Wallets
    {
        "method_id": "paypal",
        "name": "PayPal",
        "description": "Withdraw to PayPal account",
        "is_active": True,
        "supported_currencies": ["USD", "EUR", "GBP"],
        "supported_countries": [],
        "fee_type": "mixed",
        "fee_fixed": 0.30,
        "fee_percentage": 2.9,
        "fee_min": 1.0,
        "fee_max": 0,
        "min_amount": 10,
        "max_amount": 10000,
        "processing_days": 1,
        "requires_verification": False,
        "icon": "paypal",
        "sort_order": 10,
        "metadata": {
            "required_fields": ["email", "account_holder_name"],
            "optional_fields": []
        }
    },
    {
        "method_id": "wise",
        "name": "Wise (TransferWise)",
        "description": "Low-fee international transfers",
        "is_active": True,
        "supported_currencies": ["USD", "EUR", "GBP", "INR"],
        "supported_countries": [],
        "fee_type": "percentage",
        "fee_fixed": 0.0,
        "fee_percentage": 1.0,
        "fee_min": 0.50,
        "fee_max": 0,
        "min_amount": 10,
        "max_amount": 50000,
        "processing_days": 1,
        "requires_verification": False,
        "icon": "wise",
        "sort_order": 11,
        "metadata": {
            "required_fields": ["email", "account_holder_name"],
            "optional_fields": []
        }
    },
    {
        "method_id": "payoneer",
        "name": "Payoneer",
        "description": "Withdraw to Payoneer account",
        "is_active": True,
        "supported_currencies": ["USD", "EUR", "GBP"],
        "supported_countries": [],
        "fee_type": "fixed",
        "fee_fixed": 2.0,
        "fee_percentage": 0.0,
        "fee_min": 2.0,
        "fee_max": 0,
        "min_amount": 50,
        "max_amount": 10000,
        "processing_days": 2,
        "requires_verification": False,
        "icon": "payoneer",
        "sort_order": 12,
        "metadata": {
            "required_fields": ["email", "account_holder_name"],
            "optional_fields": []
        }
    },
    {
        "method_id": "skrill",
        "name": "Skrill",
        "description": "Withdraw to Skrill wallet",
        "is_active": True,
        "supported_currencies": ["USD", "EUR", "GBP"],
        "supported_countries": [],
        "fee_type": "percentage",
        "fee_fixed": 0.0,
        "fee_percentage": 3.9,
        "fee_min": 1.0,
        "fee_max": 0,
        "min_amount": 20,
        "max_amount": 10000,
        "processing_days": 1,
        "requires_verification": False,
        "icon": "skrill",
        "sort_order": 13,
        "metadata": {
            "required_fields": ["email", "account_holder_name"],
            "optional_fields": []
        }
    },
    
    # Cryptocurrency
    {
        "method_id": "crypto_usdt_trc20",
        "name": "USDT (TRC20)",
        "description": "Tether USDT on Tron network - low fees",
        "is_active": True,
        "supported_currencies": ["USDT"],
        "supported_countries": [],
        "fee_type": "fixed",
        "fee_fixed": 1.0,
        "fee_percentage": 0.0,
        "fee_min": 1.0,
        "fee_max": 0,
        "min_amount": 10,
        "max_amount": 100000,
        "processing_days": 1,
        "requires_verification": False,
        "icon": "usdt",
        "sort_order": 20,
        "metadata": {
            "required_fields": ["wallet_address"],
            "optional_fields": ["memo_tag"],
            "network": "TRC20"
        }
    },
    {
        "method_id": "crypto_usdt_erc20",
        "name": "USDT (ERC20)",
        "description": "Tether USDT on Ethereum - higher gas fees",
        "is_active": True,
        "supported_currencies": ["USDT"],
        "supported_countries": [],
        "fee_type": "fixed",
        "fee_fixed": 15.0,       # Ethereum gas fees
        "fee_percentage": 0.0,
        "fee_min": 15.0,
        "fee_max": 0,
        "min_amount": 50,        # Higher minimum due to gas
        "max_amount": 100000,
        "processing_days": 1,
        "requires_verification": False,
        "icon": "usdt",
        "sort_order": 21,
        "metadata": {
            "required_fields": ["wallet_address"],
            "optional_fields": [],
            "network": "ERC20"
        }
    },
    {
        "method_id": "crypto_usdc",
        "name": "USDC (ERC20)",
        "description": "USD Coin on Ethereum",
        "is_active": True,
        "supported_currencies": ["USDC"],
        "supported_countries": [],
        "fee_type": "fixed",
        "fee_fixed": 15.0,
        "fee_percentage": 0.0,
        "fee_min": 15.0,
        "fee_max": 0,
        "min_amount": 50,
        "max_amount": 100000,
        "processing_days": 1,
        "requires_verification": False,
        "icon": "usdc",
        "sort_order": 22,
        "metadata": {
            "required_fields": ["wallet_address"],
            "optional_fields": [],
            "network": "ERC20"
        }
    },
    
    # China-specific
    {
        "method_id": "alipay",
        "name": "Alipay",
        "description": "Withdraw to Alipay (China)",
        "is_active": False,      # Disabled by default - enable if needed
        "supported_currencies": ["USD"],
        "supported_countries": ["CN"],
        "fee_type": "percentage",
        "fee_fixed": 0.0,
        "fee_percentage": 1.0,
        "fee_min": 1.0,
        "fee_max": 0,
        "min_amount": 50,
        "max_amount": 5000,
        "processing_days": 2,
        "requires_verification": True,
        "icon": "alipay",
        "sort_order": 30,
        "metadata": {
            "required_fields": ["alipay_account", "account_holder_name"],
            "optional_fields": []
        }
    },
    {
        "method_id": "wechat_pay",
        "name": "WeChat Pay",
        "description": "Withdraw to WeChat Pay (China)",
        "is_active": False,
        "supported_currencies": ["USD"],
        "supported_countries": ["CN"],
        "fee_type": "percentage",
        "fee_fixed": 0.0,
        "fee_percentage": 1.0,
        "fee_min": 1.0,
        "fee_max": 0,
        "min_amount": 50,
        "max_amount": 5000,
        "processing_days": 2,
        "requires_verification": True,
        "icon": "wechat",
        "sort_order": 31,
        "metadata": {
            "required_fields": ["wechat_id", "account_holder_name"],
            "optional_fields": []
        }
    }
]


async def seed_withdrawal_config():
    """Seed withdrawal configuration and methods"""
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    print(f"[INFO] Connecting to {DATABASE_NAME}...")
    
    # Seed global config
    print("[INFO] Seeding withdrawal configuration...")
    
    existing_config = await db.withdrawal_config.find_one({"config_id": "global"})
    if existing_config:
        print("[INFO] Global config exists - updating...")
        await db.withdrawal_config.update_one(
            {"config_id": "global"},
            {"$set": {**WITHDRAWAL_CONFIG, "updated_at": datetime.utcnow()}}
        )
    else:
        await db.withdrawal_config.insert_one(WITHDRAWAL_CONFIG)
    
    print("[OK] Global withdrawal config seeded")
    
    # Seed withdrawal methods
    print("[INFO] Seeding withdrawal methods...")
    
    for method in WITHDRAWAL_METHODS:
        method["created_at"] = datetime.utcnow()
        method["updated_at"] = datetime.utcnow()
        
        existing = await db.withdrawal_methods.find_one({"method_id": method["method_id"]})
        if existing:
            print(f"  [UPDATE] {method['method_id']}")
            await db.withdrawal_methods.update_one(
                {"method_id": method["method_id"]},
                {"$set": {**method, "updated_at": datetime.utcnow()}}
            )
        else:
            print(f"  [CREATE] {method['method_id']}")
            await db.withdrawal_methods.insert_one(method)
    
    print(f"[OK] {len(WITHDRAWAL_METHODS)} withdrawal methods seeded")
    
    # Create indexes
    print("[INFO] Creating indexes...")
    
    await db.withdrawal_config.create_index([("config_id", 1)], unique=True)
    await db.withdrawal_methods.create_index([("method_id", 1)], unique=True)
    await db.withdrawal_methods.create_index([("is_active", 1), ("sort_order", 1)])
    await db.withdrawals.create_index([("withdrawal_id", 1)], unique=True)
    await db.withdrawals.create_index([("user_id", 1), ("created_at", -1)])
    await db.withdrawals.create_index([("status", 1), ("created_at", 1)])
    
    print("[OK] Indexes created")
    
    # Print summary
    active_methods = await db.withdrawal_methods.count_documents({"is_active": True})
    print(f"\n========== SUMMARY ==========")
    print(f"Global Config: seeded")
    print(f"Total Methods: {len(WITHDRAWAL_METHODS)}")
    print(f"Active Methods: {active_methods}")
    print(f"================================\n")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_withdrawal_config())
