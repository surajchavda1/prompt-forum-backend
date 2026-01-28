import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from dotenv import load_dotenv

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
