# ⚡ User Profile System - Quick Start

## 🎯 What Was Added

Complete user profile system with:
- Profile viewing & editing
- Avatar & cover image upload
- Statistics (reputation, ranks, badges)
- Top content (questions, answers, tags)
- Gold, Silver, Bronze badges

---

## 📁 New Files Created

1. **`app/models/auth/profile.py`** - Profile data models
2. **`app/services/auth/profile.py`** - Profile business logic
3. **`app/routes/auth/profile_routes.py`** - Profile API endpoints
4. **`app/main.py`** - Updated to include profile routes

---

## 🔄 Start Server

```bash
uvicorn app.main:app --reload
```

---

## 🧪 Test Profile (Postman/Browser)

### 1. Get User Profile

```
GET http://localhost:8000/api/users/YOUR_USER_ID/profile
```

### 2. Update Your Profile (Requires Login)

```
PUT http://localhost:8000/api/users/profile
Authorization: Bearer YOUR_TOKEN

Body (form-data):
- full_name: "Your Name"
- title: "Your Professional Title"
- location: "City, Country"
- website: "yourwebsite.com"
- about_me: "Tell us about yourself..."
```

### 3. Upload Avatar

```
POST http://localhost:8000/api/users/profile/avatar
Authorization: Bearer YOUR_TOKEN

Body (form-data):
- file: [SELECT IMAGE FILE]
```

### 4. Get User's Questions

```
GET http://localhost:8000/api/users/YOUR_USER_ID/questions
```

### 5. Get User's Answers

```
GET http://localhost:8000/api/users/YOUR_USER_ID/answers
```

---

## 📊 How Statistics Work

### Reputation Calculation

- **Post upvote:** +10 points
- **Post downvote:** -2 points
- **Answer upvote:** +10 points
- **Answer downvote:** -2 points
- **Accepted answer:** +15 points

### Global Rank

Calculated based on reputation compared to all users.

### Badges

- **Gold:** 50K+ reputation, 100+ accepted answers
- **Silver:** 5K+ reputation, 50+ accepted answers
- **Bronze:** First question/answer, 100+ reputation

---

## 🎨 Frontend Integration

### Get & Display Profile

```javascript
// Get profile
const response = await fetch(
  `http://localhost:8000/api/users/${userId}/profile`
);
const data = await response.json();

if (data.success) {
  const profile = data.data.profile;
  
  console.log('Reputation:', profile.statistics.reputation);
  console.log('Rank:', profile.statistics.global_rank);
  console.log('Badges:', profile.badges);
  console.log('Top Tags:', profile.top_tags);
}
```

### Update Profile

```javascript
const formData = new FormData();
formData.append('full_name', 'John Doe');
formData.append('title', 'AI Engineer');
formData.append('location', 'San Francisco');

const response = await fetch('http://localhost:8000/api/users/profile', {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});
```

### Upload Avatar

```javascript
const formData = new FormData();
formData.append('file', selectedFile);

const response = await fetch('http://localhost:8000/api/users/profile/avatar', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});
```

---

## 🔗 API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/{id}/profile` | Get full profile |
| PUT | `/api/users/profile` | Update own profile |
| POST | `/api/users/profile/avatar` | Upload avatar |
| POST | `/api/users/profile/cover` | Upload cover |
| GET | `/api/users/{id}/questions` | Get user's questions |
| GET | `/api/users/{id}/answers` | Get user's answers |
| GET | `/api/users/{id}/statistics` | Get stats only |
| GET | `/api/users/{id}/top-tags` | Get top tags |
| GET | `/api/users/{id}/top-posts` | Get top posts |

---

## ✅ Testing Checklist

- [ ] Get user profile - works
- [ ] Update profile - works
- [ ] Upload avatar - works
- [ ] Upload cover - works
- [ ] View questions - works
- [ ] View answers - works
- [ ] Statistics calculated correctly
- [ ] Badges awarded correctly
- [ ] Top tags showing correctly
- [ ] Top posts showing correctly

---

## 📖 Full Documentation

See **`USER_PROFILE_SYSTEM.md`** for complete documentation with:
- Detailed API specs
- Response examples
- Frontend code examples
- Badge system details
- Database schema

---

**Ready to test!** 🚀

Visit: `http://localhost:8000/docs` for interactive API documentation
