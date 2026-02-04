"""
Seed Contest Fee Configuration
Run this script to initialize dynamic contest fee settings in the database.

Usage:
    python seed_contest_config.py
"""
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "promptforum")


# ==================== GLOBAL CONTEST CONFIGURATION ====================
# Modify these settings as needed - they will be stored in MongoDB
# All values are fully dynamic and can be changed anytime via DB or admin API

CONTEST_CONFIG = {
    "config_id": "global",
    
    # ============ CONTEST CREATION FEES ============
    # Fee type: "fixed", "percentage", or "mixed"
    "creation_fee_type": "percentage",
    
    # Percentage of prize pool charged as platform fee (if type includes percentage)
    "creation_fee_percentage": 5.0,
    
    # Fixed fee amount (if type includes fixed)
    "creation_fee_fixed": 0.0,
    
    # Minimum platform fee (cap)
    "creation_fee_min": 10.0,
    
    # Maximum platform fee (cap, 0 = no cap)
    "creation_fee_max": 1000.0,
    
    # ============ PRIZE POOL REQUIREMENTS ============
    # Minimum prize pool required to create a contest
    "min_prize_pool": 100.0,
    
    # Maximum prize pool allowed
    "max_prize_pool": 1000000.0,
    
    # ============ CONTEST LIMITS ============
    # Maximum active contests per user (draft, active, upcoming)
    "max_active_contests_per_user": 5,
    
    # Maximum participants allowed per contest
    "max_participants_limit": 10000,
    
    # Minimum participants required
    "min_participants": 2,
    
    # ============ ENTRY FEE SETTINGS ============
    # Allow contest creators to set entry fees for participants
    "entry_fee_enabled": True,
    
    # Maximum entry fee as percentage of prize pool
    "entry_fee_max_percentage": 50.0,
    
    # Platform cut from entry fees (%)
    "entry_fee_platform_cut": 10.0,
    
    # ============ REFUND POLICY ============
    # Allow refunds if contest is cancelled
    "refund_on_cancel": True,
    
    # Percentage of prize pool refunded (rest kept as cancellation fee)
    "refund_percentage": 95.0,
    
    # Minimum hours before start when cancel is allowed
    "min_time_before_cancel": 24,
    
    # ============ PRIZE DISTRIBUTION ============
    # Auto-distribute prizes or require manual admin action
    "auto_distribute_prizes": False,
    
    # Days to hold prizes before auto-release
    "prize_hold_days": 7,
    
    # ============ FEATURE FLAGS ============
    # Global kill switch for contest creation
    "contest_creation_enabled": True,
    
    # Require KYC verification to create contests
    "require_kyc_for_creation": False,
    
    # Require verified email to create contests
    "require_email_verified": True,
    
    # Minimum account age (in days) to create contests
    "min_account_age_days": 0,
    
    # ============ MAINTENANCE ============
    "maintenance_mode": False,
    "maintenance_message": "",
    
    # ============ TIMESTAMPS ============
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}


async def seed_contest_config():
    """Seed the contest configuration into MongoDB"""
    print("=" * 60)
    print("Contest Fee Configuration Seeder")
    print("=" * 60)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    try:
        # ==================== CREATE/UPDATE CONFIG ====================
        print("\n[1] Seeding contest configuration...")
        
        existing = await db.contest_config.find_one({"config_id": "global"})
        
        if existing:
            # Update existing config
            CONTEST_CONFIG["updated_at"] = datetime.utcnow()
            await db.contest_config.update_one(
                {"config_id": "global"},
                {"$set": CONTEST_CONFIG}
            )
            print("    [OK] Updated existing contest configuration")
        else:
            # Insert new config
            await db.contest_config.insert_one(CONTEST_CONFIG)
            print("    [OK] Created new contest configuration")
        
        # ==================== CREATE INDEXES ====================
        print("\n[2] Creating indexes...")
        
        # contest_config index
        await db.contest_config.create_index(
            [("config_id", 1)],
            unique=True
        )
        print("    [OK] Index on contest_config.config_id")
        
        # ==================== DISPLAY CONFIG ====================
        print("\n[3] Current Configuration:")
        print("-" * 40)
        
        config = await db.contest_config.find_one({"config_id": "global"})
        
        print(f"    Fee Type: {config.get('creation_fee_type')}")
        print(f"    Fee Percentage: {config.get('creation_fee_percentage')}%")
        print(f"    Fee Fixed: {config.get('creation_fee_fixed')} credits")
        print(f"    Fee Min: {config.get('creation_fee_min')} credits")
        print(f"    Fee Max: {config.get('creation_fee_max')} credits")
        print(f"    Min Prize Pool: {config.get('min_prize_pool')} credits")
        print(f"    Max Prize Pool: {config.get('max_prize_pool')} credits")
        print(f"    Max Active Contests/User: {config.get('max_active_contests_per_user')}")
        print(f"    Refund on Cancel: {config.get('refund_percentage')}%")
        print(f"    Creation Enabled: {config.get('contest_creation_enabled')}")
        
        print("\n" + "=" * 60)
        print("Seeding complete!")
        print("\nFee Calculation Examples:")
        print("-" * 40)
        
        # Example calculations
        for prize in [100, 500, 1000, 5000, 10000]:
            fee_pct = config.get('creation_fee_percentage', 5.0)
            fee_min = config.get('creation_fee_min', 10.0)
            fee_max = config.get('creation_fee_max', 1000.0)
            
            fee = prize * (fee_pct / 100)
            fee = max(fee, fee_min)
            if fee_max > 0:
                fee = min(fee, fee_max)
            
            print(f"    Prize: {prize:>6} credits -> Fee: {fee:>6.2f} -> Total: {prize + fee:>8.2f}")
        
        print("\n" + "=" * 60)
        
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed_contest_config())
