import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from dotenv import load_dotenv
from pymongo import ASCENDING

# Load environment variables
load_dotenv()

class Database:
    client: Optional[AsyncIOMotorClient] = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        cls.client = AsyncIOMotorClient(mongodb_url)
        print("[OK] Connected to MongoDB")
        
        # Create indexes
        await cls.create_indexes()
    
    @classmethod
    async def create_indexes(cls):
        """Create database indexes"""
        db = cls.get_db()
        
        # Users collection indexes
        # Unique index on username (case-insensitive using collation)
        try:
            await db.users.create_index(
                [("username", ASCENDING)],
                unique=True,
                sparse=True,  # Allow null/missing values
                collation={"locale": "en", "strength": 2}  # Case-insensitive
            )
            print("[OK] Created unique index on users.username")
        except Exception as e:
            print(f"[WARN] Index on users.username may already exist: {e}")
        
        # Wallet indexes
        try:
            await db.wallets.create_index([("user_id", ASCENDING)], unique=True)
            print("[OK] Created unique index on wallets.user_id")
        except Exception as e:
            print(f"[WARN] Index on wallets.user_id may already exist: {e}")
        
        # Transaction indexes
        try:
            await db.wallet_transactions.create_index([("user_id", ASCENDING), ("created_at", -1)])
            await db.wallet_transactions.create_index([("transaction_id", ASCENDING)], unique=True)
            await db.wallet_transactions.create_index([("idempotency_key", ASCENDING)], sparse=True)
            print("[OK] Created indexes on wallet_transactions")
        except Exception as e:
            print(f"[WARN] Indexes on wallet_transactions may already exist: {e}")
        
        # Payment orders indexes
        try:
            await db.payment_orders.create_index([("order_id", ASCENDING)], unique=True)
            await db.payment_orders.create_index([("user_id", ASCENDING), ("created_at", -1)])
            await db.payment_orders.create_index([("gateway_order_id", ASCENDING)], sparse=True)
            print("[OK] Created indexes on payment_orders")
        except Exception as e:
            print(f"[WARN] Indexes on payment_orders may already exist: {e}")
        
        # Withdrawal indexes
        try:
            await db.withdrawals.create_index([("withdrawal_id", ASCENDING)], unique=True)
            await db.withdrawals.create_index([("user_id", ASCENDING), ("created_at", -1)])
            await db.withdrawals.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
            await db.withdrawals.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
            print("[OK] Created indexes on withdrawals")
        except Exception as e:
            print(f"[WARN] Indexes on withdrawals may already exist: {e}")
        
        # Withdrawal configuration indexes (dynamic settings)
        try:
            await db.withdrawal_config.create_index([("config_id", ASCENDING)], unique=True)
            print("[OK] Created index on withdrawal_config")
        except Exception as e:
            print(f"[WARN] Index on withdrawal_config may already exist: {e}")
        
        # Withdrawal methods indexes (dynamic payment methods)
        try:
            await db.withdrawal_methods.create_index([("method_id", ASCENDING)], unique=True)
            await db.withdrawal_methods.create_index([("is_active", ASCENDING), ("sort_order", ASCENDING)])
            print("[OK] Created indexes on withdrawal_methods")
        except Exception as e:
            print(f"[WARN] Indexes on withdrawal_methods may already exist: {e}")
        
        # Contest configuration indexes (dynamic contest fees)
        try:
            await db.contest_config.create_index([("config_id", ASCENDING)], unique=True)
            print("[OK] Created index on contest_config")
        except Exception as e:
            print(f"[WARN] Index on contest_config may already exist: {e}")
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            print("[OK] Disconnected from MongoDB")
    
    @classmethod
    def get_db(cls):
        """Get database instance"""
        database_name = os.getenv("DATABASE_NAME", "promptforum")
        return cls.client[database_name]


async def get_database():
    """Dependency to get database"""
    return Database.get_db()
