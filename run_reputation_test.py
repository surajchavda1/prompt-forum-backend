# -*- coding: utf-8 -*-
"""
Real Integration Test: Reputation, Rank & Badge System
NO MOCKS - 100% Real Database Flow
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from bson import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "promptforum")

print("=" * 80)
print("REAL REPUTATION SYSTEM TEST")
print("=" * 80)
print(f"Database: {DB_NAME}")
print("=" * 80)


async def run_test():
    # Connect to database
    print("\n[1/10] Connecting to database...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    print("[OK] Connected")
    
    test_user_id = "6974a0edd85365885aac6fb4"
    
    try:
        # Step 1: Create a test post
        print("\n[2/10] Creating test post...")
        post = {
            "title": f"Test: Reputation System Test {datetime.utcnow().timestamp()}",
            "slug": f"test-rep-{datetime.utcnow().timestamp()}",
            "body": "Testing reputation calculations",
            "author_id": test_user_id,
            "author_name": "Test User",
            "category_id": "test",
            "tags": ["test"],
            "upvote_count": 0,
            "downvote_count": 0,
            "upvoters": [],
            "downvoters": [],
            "view_count": 10,
            "reply_count": 0,
            "is_pinned": False,
            "is_locked": False,
            "is_solved": False,
            "attachments": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await db.posts.insert_one(post)
        post_id = str(result.inserted_id)
        print(f"[OK] Created post: {post_id}")
        
        # Step 2: Add 5 upvotes to post
        print("\n[3/10] Adding 5 upvotes to post...")
        upvoters = [str(ObjectId()) for _ in range(5)]
        await db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"upvote_count": 5, "upvoters": upvoters}}
        )
        print("[OK] Added 5 upvotes (+50 reputation)")
        
        # Step 3: Add 1 downvote to post
        print("\n[4/10] Adding 1 downvote to post...")
        await db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"downvote_count": 1, "downvoters": [str(ObjectId())]}}
        )
        print("[OK] Added 1 downvote (-2 reputation)")
        
        # Step 4: Create an answer
        print("\n[5/10] Creating test answer...")
        answer = {
            "post_id": post_id,
            "parent_id": None,
            "author_id": test_user_id,
            "author_name": "Test User",
            "body": "Test answer for reputation calculation",
            "upvote_count": 0,
            "downvote_count": 0,
            "upvoters": [],
            "downvoters": [],
            "reply_count": 0,
            "is_accepted": False,
            "is_edited": False,
            "is_post_comment": False,
            "attachments": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await db.comments.insert_one(answer)
        answer_id = str(result.inserted_id)
        print(f"[OK] Created answer: {answer_id}")
        
        # Step 5: Add 10 upvotes to answer
        print("\n[6/10] Adding 10 upvotes to answer...")
        upvoters = [str(ObjectId()) for _ in range(10)]
        await db.comments.update_one(
            {"_id": ObjectId(answer_id)},
            {"$set": {"upvote_count": 10, "upvoters": upvoters}}
        )
        print("[OK] Added 10 upvotes (+100 reputation)")
        
        # Step 6: Mark answer as accepted
        print("\n[7/10] Marking answer as accepted...")
        await db.comments.update_one(
            {"_id": ObjectId(answer_id)},
            {"$set": {"is_accepted": True}}
        )
        print("[OK] Answer accepted (+15 reputation)")
        
        # Step 7: Calculate expected reputation
        print("\n[8/10] Calculating expected reputation...")
        expected_rep = (5 * 10) - (1 * 2) + (10 * 10) + 15
        print(f"  Post: (5 upvotes x 10) - (1 downvote x 2) = 48")
        print(f"  Answer: (10 upvotes x 10) = 100")
        print(f"  Accepted bonus: 15")
        print(f"  TOTAL EXPECTED: {expected_rep} reputation")
        
        # Step 8: Get actual reputation from ProfileService
        print("\n[9/10] Verifying actual reputation from database...")
        from app.services.auth.profile import ProfileService
        
        profile_service = ProfileService(db)
        stats = await profile_service.calculate_user_statistics(test_user_id)
        badges = await profile_service.calculate_user_badges(test_user_id, stats)
        
        print("\n" + "=" * 80)
        print("ACTUAL RESULTS FROM DATABASE")
        print("=" * 80)
        print(f"Reputation: {stats['reputation']}")
        print(f"Global Rank: #{stats['global_rank']}")
        print(f"Accepted Answers: {stats['accepted_answers']}")
        print(f"Total Questions: {stats['total_questions']}")
        print(f"Total Answers: {stats['total_answers']}")
        print(f"Total Views: {stats['total_views']}")
        print(f"\nBadges:")
        print(f"  Gold: {badges['gold']}")
        print(f"  Silver: {badges['silver']}")
        print(f"  Bronze: {badges['bronze']}")
        
        # Step 9: Verify correctness
        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)
        
        rep_match = stats['reputation'] == expected_rep
        print(f"\nReputation Check:")
        print(f"  Expected: {expected_rep}")
        print(f"  Actual: {stats['reputation']}")
        print(f"  Status: {'[PASS]' if rep_match else '[FAIL]'}")
        
        # Check badge expectations
        expected_badges = {"gold": 0, "silver": 0, "bronze": 2}
        
        # With reputation 163, 2 questions, 1 answer, 1 accepted:
        # Bronze: First question + First answer = 2
        
        badges_match = badges == expected_badges
        print(f"\nBadge Check:")
        print(f"  Expected: Gold={expected_badges['gold']}, Silver={expected_badges['silver']}, Bronze={expected_badges['bronze']}")
        print(f"  Actual: Gold={badges['gold']}, Silver={badges['silver']}, Bronze={badges['bronze']}")
        print(f"  Status: {'[PASS]' if badges_match else '[FAIL]'}")
        
        print(f"\nBadge Breakdown:")
        if stats['total_questions'] >= 1:
            print("  [OK] Bronze: First question")
        if stats['total_answers'] >= 1:
            print("  [OK] Bronze: First answer")
        if stats['reputation'] >= 100:
            print("  [OK] Bronze: Supporter (100+ reputation)")
        if stats['accepted_answers'] >= 1:
            print("  [OK] Bronze: Scholar (first accepted answer)")
        
        if rep_match and badges_match:
            print("\n[SUCCESS] ALL TESTS PASSED!")
        else:
            print("\n[WARN] Some tests failed - check output above")
        
        # Cleanup
        print("\n[10/10] Cleanup...")
        print("Test data remains in database for inspection.")
        print(f"  Post ID: {post_id}")
        print(f"  Answer ID: {answer_id}")
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n[OK] Database connection closed")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_test())
