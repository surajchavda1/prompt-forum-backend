# 🎯 Reputation, Rank & Badge System - Complete Explanation

## 📊 How Stats Are Calculated

### 1. Reputation System

**Formula:** Points from votes and accepted answers

#### Points Earned:
| Action | Points |
|--------|--------|
| Your question gets upvoted | **+10** |
| Your answer gets upvoted | **+10** |
| Your answer is accepted | **+15** |

#### Points Lost:
| Action | Points |
|--------|--------|
| Your question gets downvoted | **-2** |
| Your answer gets downvoted | **-2** |

**Minimum:** 0 (reputation cannot be negative)

**Example:**
```
You have 1 question with:
- 5 upvotes = +50 points
- 1 downvote = -2 points
- Total reputation = 48 points

You have 2 answers with:
- Answer 1: 10 upvotes, 0 downvotes, accepted = (10*10) + 15 = 115 points
- Answer 2: 3 upvotes, 1 downvote = (3*10) - 2 = 28 points
- Total reputation = 48 + 115 + 28 = 191 points
```

---

### 2. Global Rank

**Formula:** Position based on reputation compared to all users

**How it works:**
1. Count how many users have **more reputation** than you
2. Your rank = that count + 1

**Example:**
```
User A: 10,000 reputation → Rank #1
User B: 5,000 reputation → Rank #2
User C: 2,000 reputation → Rank #3
You: 500 reputation → Rank #4
```

**Special case:** If you're the only user or have the highest reputation, your rank is **#1**.

---

### 3. Badge System

Badges are **auto-awarded** based on achievements. Each badge is independent.

#### 🥇 Gold Badges (Rare Achievements)

| Badge | Requirement |
|-------|-------------|
| Legendary | Reputation ≥ 50,000 |
| Epic | Reputation ≥ 25,000 |
| Fantastic | Reputation ≥ 10,000 |
| Great Answer | 100+ accepted answers |
| Legendary Answerer | 500+ accepted answers |
| Famous | 1,000,000+ total views on your questions |

**Maximum possible:** 6 gold badges

---

#### 🥈 Silver Badges (Notable Achievements)

| Badge | Requirement |
|-------|-------------|
| Notable | Reputation ≥ 5,000 |
| Good | Reputation ≥ 2,500 |
| Nice | Reputation ≥ 1,000 |
| Enlightened | 50+ accepted answers |
| Guru | 25+ accepted answers |
| Inquisitive | 50+ questions posted |
| Prolific | 100+ answers posted |
| Popular | 100,000+ total views |

**Maximum possible:** 8 silver badges

---

#### 🥉 Bronze Badges (Common Achievements)

| Badge | Requirement |
|-------|-------------|
| **Curious** | Posted 1st question |
| **Student** | Posted 1st answer |
| Supporter | Reputation ≥ 100 |
| Teacher | Reputation ≥ 500 |
| Scholar | 1st accepted answer |
| Knowledgeable | 10+ accepted answers |
| Contributor | 10+ questions |
| Active | 10+ answers |
| Engaged | 50+ answers |

**Maximum possible:** 9 bronze badges

---

## 🧮 Your Current Stats Breakdown

**Your Stats:**
- Questions: 1
- Answers: 0
- Upvotes on questions: 0
- Downvotes on questions: 0
- Upvotes on answers: 0
- Downvotes on answers: 0
- Accepted answers: 0
- Total views: 17

**Reputation Calculation:**
```
Questions: (0 upvotes × 10) - (0 downvotes × 2) = 0 points
Answers: (0 upvotes × 10) - (0 downvotes × 2) + (0 accepted × 15) = 0 points
Total Reputation = 0 points
```

**Global Rank Calculation:**
```
Users with higher reputation: 0
Your rank = 0 + 1 = #1
```

**Badge Calculation:**

🥇 **Gold Badges: 0**
- ❌ Reputation ≥ 50,000? NO (0 < 50,000)
- ❌ Reputation ≥ 25,000? NO (0 < 25,000)
- ❌ Reputation ≥ 10,000? NO (0 < 10,000)
- ❌ 100+ accepted? NO (0 < 100)
- ❌ 500+ accepted? NO (0 < 500)
- ❌ 1M+ views? NO (17 < 1,000,000)

🥈 **Silver Badges: 0**
- ❌ Reputation ≥ 5,000? NO (0 < 5,000)
- ❌ Reputation ≥ 2,500? NO (0 < 2,500)
- ❌ Reputation ≥ 1,000? NO (0 < 1,000)
- ❌ 50+ accepted? NO (0 < 50)
- ❌ 25+ accepted? NO (0 < 25)
- ❌ 50+ questions? NO (1 < 50)
- ❌ 100+ answers? NO (0 < 100)
- ❌ 100K+ views? NO (17 < 100,000)

🥉 **Bronze Badges: 1**
- ✅ **1+ questions? YES (1 ≥ 1)** → "Curious" badge
- ❌ 1+ answers? NO (0 < 1)
- ❌ Reputation ≥ 100? NO (0 < 100)
- ❌ Reputation ≥ 500? NO (0 < 500)
- ❌ 1+ accepted? NO (0 < 1)
- ❌ 10+ accepted? NO (0 < 10)
- ❌ 10+ questions? NO (1 < 10)
- ❌ 10+ answers? NO (0 < 10)
- ❌ 50+ answers? NO (0 < 50)

---

## ✅ Your Correct Profile Should Show:

```
Reputation: 0
Global Rank: #1
Accepted Answers: 0
Questions: 1
Impact: 17

Badges:
🥇 0 Gold
🥈 0 Silver  ← NOT 1!
🥉 1 Bronze  ← "Curious" badge for first question
```

---

## 🔍 If You're Seeing Different Numbers

### Frontend Bug
If the API returns correct values but the frontend shows wrong ones, it's a frontend display bug. Check your frontend code.

### Backend Bug
If the API itself returns wrong values, there's a backend calculation error.

---

## 🎯 How to Earn More Reputation

**Quick wins:**
1. **Post great answers** → +10 per upvote
2. **Get answers accepted** → +15 bonus
3. **Post helpful questions** → +10 per upvote

**Example path to 1000 reputation:**
- Post 20 answers, each gets 4 upvotes and 1 accepted
- 20 answers × (4 upvotes × 10 + 15 accepted) = 20 × 55 = 1,100 points
- You'd earn: 1 Bronze + 1 Silver badge!

---

## 📈 Badge Progression Example

### User Journey:

**Week 1:** Post first question
- ✅ Earned "Curious" (Bronze)
- Badges: 0🥇 0🥈 1🥉

**Month 1:** Post 10 answers, 3 accepted
- ✅ Earned "Student" (Bronze) - 1st answer
- ✅ Earned "Scholar" (Bronze) - 1st accepted
- Badges: 0🥇 0🥈 3🥉

**Month 3:** 500+ reputation
- ✅ Earned "Supporter" (Bronze) - 100+ rep
- ✅ Earned "Teacher" (Bronze) - 500+ rep
- Badges: 0🥇 0🥈 5🥉

**Year 1:** 1,000+ reputation, 25 accepted
- ✅ Earned "Nice" (Silver) - 1000+ rep
- ✅ Earned "Guru" (Silver) - 25+ accepted
- Badges: 0🥇 2🥈 5🥉

**Year 2:** 10,000+ reputation, 100 accepted
- ✅ Earned "Fantastic" (Gold) - 10k+ rep
- ✅ Earned "Great Answer" (Gold) - 100+ accepted
- Badges: 2🥇 2🥈 5🥉

---

## 🔧 API Endpoints to Check Your Stats

### Get full profile
```bash
GET /api/users/{user_id}/profile
```

### Get just statistics
```bash
GET /api/users/{user_id}/statistics
```

---

**Status:** Stats calculated in real-time from database  
**Date:** January 26, 2026  
**Frequency:** Recalculated on every API call (no caching)
