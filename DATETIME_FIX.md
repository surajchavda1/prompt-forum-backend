# ✅ Fixed: Datetime Serialization Errors

## Problem

```
TypeError: Object of type datetime is not JSON serializable
```

Multiple endpoints returned 500 errors because datetime objects weren't being converted to JSON-compatible strings:
1. `GET /api/users/{id}/profile` - 500 error
2. `GET /api/users/{id}/questions` - 500 error
3. `GET /api/users/{id}/answers` - 500 error (potential)

---

## Root Cause

Datetime fields in multiple places weren't being converted to ISO format strings before JSON serialization:
1. `joined_date` (from `user.created_at`)
2. `created_at` in `top_posts` array
3. `uploaded_at` in post/answer `attachments` arrays

---

## Fixes Applied

### 1. Fixed `joined_date` in `get_user_profile()`

**Before:**
```python
"joined_date": user.get("created_at"),
```

**After:**
```python
"joined_date": user.get("created_at").isoformat() if user.get("created_at") else None,
```

### 2. Fixed `created_at` in `get_user_top_posts()`

**Before:**
```python
"created_at": post.get("created_at"),
```

**After:**
```python
"created_at": post.get("created_at").isoformat() if post.get("created_at") else None,
```

### 3. Fixed `attachments.uploaded_at` in `get_user_posts()`

**Before:**
```python
for post in posts:
    post["id"] = str(post["_id"])
    del post["_id"]
    if post.get("created_at"):
        post["created_at"] = post["created_at"].isoformat()
    if post.get("updated_at"):
        post["updated_at"] = post["updated_at"].isoformat()
```

**After:**
```python
for post in posts:
    post["id"] = str(post["_id"])
    del post["_id"]
    if post.get("created_at"):
        post["created_at"] = post["created_at"].isoformat()
    if post.get("updated_at"):
        post["updated_at"] = post["updated_at"].isoformat()
    
    # Convert datetime in attachments
    if post.get("attachments"):
        for attachment in post["attachments"]:
            if attachment.get("uploaded_at"):
                attachment["uploaded_at"] = attachment["uploaded_at"].isoformat()
```

### 4. Fixed `attachments.uploaded_at` in `get_user_answers()`

Same fix applied to answer attachments.

---

## File Modified

- `app/services/auth/profile.py`

---

## Test Now

**Server should auto-reload if you're running with `--reload` flag:**

```bash
# If you see "Application startup complete" in logs, just test:
GET http://localhost:8000/api/users/6974a0edd85365885aac6fb4/profile
```

**If server didn't auto-reload, restart manually:**

```bash
# Ctrl+C to stop
uvicorn app.main:app --reload
```

**Expected Response (200 OK):**

```json
{
  "success": true,
  "message": "Profile retrieved successfully",
  "data": {
    "profile": {
      "id": "6974a0edd85365885aac6fb4",
      "email": "test@example.com",
      "full_name": "Test User",
      "joined_date": "2026-01-26T10:30:00.123456",
      "statistics": {
        "reputation": 0,
        "global_rank": 1,
        "accepted_answers": 0,
        "total_answers": 0,
        "total_questions": 0,
        "total_views": 0,
        "impact": 0
      },
      "badges": {
        "gold": 0,
        "silver": 0,
        "bronze": 0
      },
      "top_tags": [],
      "top_posts": []
    }
  }
}
```

---

## Status

✅ **Fixed!** Server should auto-reload, or restart manually if needed.

**Date:** January 26, 2026
