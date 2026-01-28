"""
Test actual API responses to verify badge calculation
"""
import requests
import json

USER_ID = "6974a0edd85365885aac6fb4"
BASE_URL = "http://localhost:8000"

print("=" * 60)
print("Testing Profile API Responses")
print("=" * 60)

# Test 1: Get Statistics
print("\n1. GET /api/users/{id}/statistics")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/api/users/{USER_ID}/statistics")
    if response.status_code == 200:
        data = response.json()
        print(f"Status: {response.status_code} OK")
        print(f"\nResponse:")
        print(json.dumps(data, indent=2))
        
        # Extract badges
        if data.get("success") and data.get("data"):
            badges = data["data"].get("badges", {})
            stats = data["data"].get("statistics", {})
            
            print(f"\n--- Extracted Data ---")
            print(f"Reputation: {stats.get('reputation')}")
            print(f"Rank: #{stats.get('global_rank')}")
            print(f"Questions: {stats.get('total_questions')}")
            print(f"Answers: {stats.get('total_answers')}")
            print(f"Accepted: {stats.get('accepted_answers')}")
            print(f"\nBadges:")
            print(f"  Gold: {badges.get('gold')}")
            print(f"  Silver: {badges.get('silver')}")
            print(f"  Bronze: {badges.get('bronze')}")
            
            # Verify correctness
            if badges.get('silver') == 0:
                print(f"\n[PASS] Backend returns correct silver badge count: 0")
            else:
                print(f"\n[FAIL] Backend returns WRONG silver badge count: {badges.get('silver')}")
                print(f"       Expected: 0")
                print(f"       This is a BACKEND BUG!")
    else:
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {str(e)}")

# Test 2: Get Full Profile
print("\n\n2. GET /api/users/{id}/profile")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/api/users/{USER_ID}/profile")
    if response.status_code == 200:
        data = response.json()
        print(f"Status: {response.status_code} OK")
        
        if data.get("success") and data.get("data"):
            profile = data["data"].get("profile", {})
            badges = profile.get("badges", {})
            stats = profile.get("statistics", {})
            
            print(f"\n--- Profile Badges ---")
            print(f"  Gold: {badges.get('gold')}")
            print(f"  Silver: {badges.get('silver')}")
            print(f"  Bronze: {badges.get('bronze')}")
            
            # Verify correctness
            if badges.get('silver') == 0:
                print(f"\n[PASS] Profile returns correct silver badge count: 0")
            else:
                print(f"\n[FAIL] Profile returns WRONG silver badge count: {badges.get('silver')}")
                print(f"       Expected: 0")
                print(f"       This is a BACKEND BUG!")
    else:
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {str(e)}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
