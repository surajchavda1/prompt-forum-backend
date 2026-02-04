"""
Payment System Seeder
Seeds credit packages and gateway configurations
Run: python seed_payment.py
"""
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "promptforum")


async def seed_credit_packages(db):
    """Seed predefined credit packages"""
    
    packages = [
        {
            "package_id": "starter",
            "name": "Starter Pack",
            "description": "Perfect for trying out the platform",
            "price": 99,
            "credits": 100,
            "bonus_credits": 0,
            "total_credits": 100,
            "currency": "INR",
            "discount_percentage": 0,
            "original_price": None,
            "min_quantity": 1,
            "max_quantity": 1,
            "is_popular": False,
            "is_best_value": False,
            "badge": None,
            "sort_order": 1,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "package_id": "basic",
            "name": "Basic Pack",
            "description": "Great for regular participants",
            "price": 249,
            "credits": 250,
            "bonus_credits": 25,
            "total_credits": 275,
            "currency": "INR",
            "discount_percentage": 10,
            "original_price": 275,
            "min_quantity": 1,
            "max_quantity": 1,
            "is_popular": False,
            "is_best_value": False,
            "badge": None,
            "sort_order": 2,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "package_id": "popular",
            "name": "Popular Pack",
            "description": "Most popular choice among users",
            "price": 499,
            "credits": 500,
            "bonus_credits": 75,
            "total_credits": 575,
            "currency": "INR",
            "discount_percentage": 15,
            "original_price": 575,
            "min_quantity": 1,
            "max_quantity": 1,
            "is_popular": True,
            "is_best_value": False,
            "badge": "Most Popular",
            "sort_order": 3,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "package_id": "pro",
            "name": "Pro Pack",
            "description": "For serious competitors and creators",
            "price": 999,
            "credits": 1000,
            "bonus_credits": 200,
            "total_credits": 1200,
            "currency": "INR",
            "discount_percentage": 20,
            "original_price": 1200,
            "min_quantity": 1,
            "max_quantity": 1,
            "is_popular": False,
            "is_best_value": True,
            "badge": "Best Value",
            "sort_order": 4,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "package_id": "premium",
            "name": "Premium Pack",
            "description": "Maximum credits with maximum savings",
            "price": 2499,
            "credits": 2500,
            "bonus_credits": 750,
            "total_credits": 3250,
            "currency": "INR",
            "discount_percentage": 30,
            "original_price": 3250,
            "min_quantity": 1,
            "max_quantity": 1,
            "is_popular": False,
            "is_best_value": False,
            "badge": "Premium",
            "sort_order": 5,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "package_id": "enterprise",
            "name": "Enterprise Pack",
            "description": "For businesses and contest organizers",
            "price": 4999,
            "credits": 5000,
            "bonus_credits": 2000,
            "total_credits": 7000,
            "currency": "INR",
            "discount_percentage": 40,
            "original_price": 7000,
            "min_quantity": 1,
            "max_quantity": 1,
            "is_popular": False,
            "is_best_value": False,
            "badge": "Enterprise",
            "sort_order": 6,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    # Clear existing packages
    await db.credit_packages.delete_many({})
    
    # Insert packages
    result = await db.credit_packages.insert_many(packages)
    print(f"[OK] Seeded {len(result.inserted_ids)} credit packages")


async def seed_gateway_configs(db):
    """Seed payment gateway configurations"""
    
    gateways = [
        {
            "gateway_id": "cashfree",
            "name": "Cashfree Payments",
            "description": "Pay via UPI, Cards, Net Banking, Wallets",
            "status": "active",
            "is_default": True,
            "platform_fee_percentage": 0.0,
            "platform_fee_fixed": 0.0,
            "gateway_fee_percentage": 2.0,
            "gateway_fee_fixed": 0.0,
            "min_amount": 1.0,
            "max_amount": 100000.0,
            "supports_refund": True,
            "supports_partial_refund": True,
            "supports_subscription": False,
            "supported_currencies": ["INR"],
            "is_sandbox": True,
            # Return URL after payment - use {order_id} as placeholder
            "return_url": "http://localhost:3000/payment/status?order_id={order_id}",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        # Add more gateways as needed:
        # {
        #     "gateway_id": "razorpay",
        #     "name": "Razorpay",
        #     ...
        # },
    ]
    
    # Clear existing configs
    await db.payment_gateway_configs.delete_many({})
    
    # Insert configs
    result = await db.payment_gateway_configs.insert_many(gateways)
    print(f"[OK] Seeded {len(result.inserted_ids)} gateway configurations")


async def create_indexes(db):
    """Create indexes for payment collections"""
    
    # Credit packages
    await db.credit_packages.create_index("package_id", unique=True)
    await db.credit_packages.create_index("status")
    await db.credit_packages.create_index("sort_order")
    print("[OK] Created indexes for credit_packages")
    
    # Gateway configs
    await db.payment_gateway_configs.create_index("gateway_id", unique=True)
    await db.payment_gateway_configs.create_index("status")
    print("[OK] Created indexes for payment_gateway_configs")
    
    # Wallets
    await db.wallets.create_index("user_id", unique=True)
    await db.wallets.create_index("status")
    print("[OK] Created indexes for wallets")
    
    # Transactions
    await db.wallet_transactions.create_index("transaction_id", unique=True)
    await db.wallet_transactions.create_index([("user_id", 1), ("created_at", -1)])
    await db.wallet_transactions.create_index("idempotency_key", sparse=True)
    await db.wallet_transactions.create_index("category")
    print("[OK] Created indexes for wallet_transactions")
    
    # Payment orders
    await db.payment_orders.create_index("order_id", unique=True)
    await db.payment_orders.create_index([("user_id", 1), ("created_at", -1)])
    await db.payment_orders.create_index("gateway_order_id", sparse=True)
    await db.payment_orders.create_index("status")
    print("[OK] Created indexes for payment_orders")


async def main():
    """Main seeder function"""
    print("=" * 50)
    print("Payment System Seeder")
    print("=" * 50)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    try:
        # Create indexes
        print("\n[1/3] Creating indexes...")
        await create_indexes(db)
        
        # Seed credit packages
        print("\n[2/3] Seeding credit packages...")
        await seed_credit_packages(db)
        
        # Seed gateway configs
        print("\n[3/3] Seeding gateway configurations...")
        await seed_gateway_configs(db)
        
        print("\n" + "=" * 50)
        print("[SUCCESS] Payment system seeded successfully!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n[ERROR] Seeding failed: {str(e)}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
