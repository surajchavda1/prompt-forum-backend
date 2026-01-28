"""
Test badge calculation logic to verify correctness.

Run this to test badge calculation with your current stats.
"""

def calculate_badges(reputation: int, accepted: int, questions: int, answers: int, total_views: int) -> dict:
    """
    Calculate user badges based on achievements.
    """
    gold = 0
    silver = 0
    bronze = 0
    
    # Gold badges (rare achievements)
    if reputation >= 50000:
        gold += 1
    if reputation >= 25000:
        gold += 1
    if reputation >= 10000:
        gold += 1
    if accepted >= 100:
        gold += 1
    if accepted >= 500:
        gold += 1
    if total_views >= 1000000:
        gold += 1
    
    # Silver badges (notable achievements)
    if reputation >= 5000:
        silver += 1
    if reputation >= 2500:
        silver += 1
    if reputation >= 1000:
        silver += 1
    if accepted >= 50:
        silver += 1
    if accepted >= 25:
        silver += 1
    if questions >= 50:
        silver += 1
    if answers >= 100:
        silver += 1
    if total_views >= 100000:
        silver += 1
    
    # Bronze badges (common achievements)
    if questions >= 1:
        bronze += 1  # Asked first question
    if answers >= 1:
        bronze += 1  # Posted first answer
    if reputation >= 100:
        bronze += 1
    if reputation >= 500:
        bronze += 1
    if accepted >= 1:
        bronze += 1  # First accepted answer
    if accepted >= 10:
        bronze += 1
    if questions >= 10:
        bronze += 1
    if answers >= 10:
        bronze += 1
    if answers >= 50:
        bronze += 1
    
    return {
        "gold": gold,
        "silver": silver,
        "bronze": bronze
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Badge Calculation Test")
    print("=" * 60)
    
    # Test with user's actual stats
    test_cases = [
        {
            "name": "Current User Stats",
            "reputation": 0,
            "accepted": 0,
            "questions": 1,
            "answers": 0,
            "total_views": 17,
            "expected": {"gold": 0, "silver": 0, "bronze": 1}
        },
        {
            "name": "New User (Empty)",
            "reputation": 0,
            "accepted": 0,
            "questions": 0,
            "answers": 0,
            "total_views": 0,
            "expected": {"gold": 0, "silver": 0, "bronze": 0}
        },
        {
            "name": "Moderate User",
            "reputation": 1500,
            "accepted": 10,
            "questions": 5,
            "answers": 20,
            "total_views": 5000,
            "expected": {"gold": 0, "silver": 1, "bronze": 4}
        },
        {
            "name": "Power User",
            "reputation": 10000,
            "accepted": 100,
            "questions": 50,
            "answers": 150,
            "total_views": 100000,
            "expected": {"gold": 2, "silver": 5, "bronze": 9}
        }
    ]
    
    for test in test_cases:
        print(f"\n{test['name']}:")
        print(f"  Reputation: {test['reputation']}")
        print(f"  Accepted: {test['accepted']}")
        print(f"  Questions: {test['questions']}")
        print(f"  Answers: {test['answers']}")
        print(f"  Total Views: {test['total_views']}")
        
        result = calculate_badges(
            test['reputation'],
            test['accepted'],
            test['questions'],
            test['answers'],
            test['total_views']
        )
        
        print(f"\n  Calculated Badges:")
        print(f"    Gold: {result['gold']}")
        print(f"    Silver: {result['silver']}")
        print(f"    Bronze: {result['bronze']}")
        
        print(f"\n  Expected Badges:")
        print(f"    Gold: {test['expected']['gold']}")
        print(f"    Silver: {test['expected']['silver']}")
        print(f"    Bronze: {test['expected']['bronze']}")
        
        # Check if correct
        if result == test['expected']:
            print(f"\n  [PASS]")
        else:
            print(f"\n  [FAIL] - Badge calculation incorrect!")
            print(f"     Expected: {test['expected']}")
            print(f"     Got: {result}")
        
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
