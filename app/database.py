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
