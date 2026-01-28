```markdown
# 👤 User Profile System - Complete Documentation

## Overview

Complete user profile system with:
- ✅ Profile viewing (public)
- ✅ Profile editing (own profile)
- ✅ Statistics calculation (reputation, ranks, badges)
- ✅ Top content (posts, tags)
- ✅ Avatar & cover image upload
- ✅ Questions & answers listing
- ✅ Badge system (gold, silver, bronze)

---

## 📡 API Endpoints

### 1. Get User Profile (Public)

```http
GET /api/users/{user_id}/profile
```

**Description:** Get complete user profile with all statistics and content.

**Response:**
```json
{
  "success": true,
  "message": "Profile retrieved successfully",
  "data": {
    "profile": {
      "id": "6974a0edd85365885aac6fb4",
      "email": "promptwizard@example.com",
      "full_name": "PromptWizard",
      "username": "promptwizard",
      "profile_picture": "http://localhost:8000/uploads/avatar.jpg",
      "cover_image": "http://localhost:8000/uploads/cover.jpg",
      "title": "Senior AI Prompt Engineer | Specializing in ChatGPT & Claude",
      "location": "San Francisco, CA",
      "website": "promptwizard.dev",
      "about_me": "Passionate about bridging the gap between human intent and AI execution. With over 3 years of experience in prompt engineering, I help businesses leverage LLMs for better efficiency. Top 1% contributor on PromptOverflow.",
      "is_verified": true,
      "joined_date": "2023-01-15T00:00:00",
      "statistics": {
        "reputation": 45230,
        "global_rank": 127,
        "accepted_answers": 971,
        "total_answers": 1245,
        "total_questions": 89,
        "total_views": 1200000,
        "impact": 1200000
      },
      "badges": {
        "gold": 15,
        "silver": 42,
        "bronze": 89
      },
      "top_tags": [
        {"name": "chatgpt", "count": 1245},
        {"name": "midjourney", "count": 890},
        {"name": "claude", "count": 756},
        {"name": "prompt-engineering", "count": 654},
        {"name": "dall-e", "count": 432}
      ],
      "top_posts": [
        {
          "id": "69774586151dd03ac5e7df75",
          "title": "How to write a prompt that generates consistent character designs across multiple images?",
          "upvote_count": 452,
          "view_count": 12500,
          "reply_count": 34,
          "created_at": "2026-01-15T10:30:00",
          "is_solved": true
        }
      ]
    }
  }
}
```

---

### 2. Update Own Profile

```http
PUT /api/users/profile
```

**Authentication:** Required

**Body (form-data):**
- `full_name` (string, optional, 1-100 chars)
- `title` (string, optional, max 200 chars)
- `location` (string, optional, max 100 chars)
- `website` (string, optional, max 200 chars)
- `about_me` (string, optional, max 5000 chars)

**Example:**
```bash
curl -X PUT http://localhost:8000/api/users/profile \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "full_name=PromptWizard" \
  -F "title=Senior AI Prompt Engineer | Specializing in ChatGPT & Claude | Open to consulting" \
  -F "location=San Francisco, CA" \
  -F "website=promptwizard.dev" \
  -F "about_me=Passionate about bridging the gap between human intent and AI execution..."
```

**Response:**
```json
{
  "success": true,
  "message": "Profile updated successfully",
  "data": {
    "profile": { /* Full updated profile */ }
  }
}
```

---

### 3. Upload Profile Picture

```http
POST /api/users/profile/avatar
```

**Authentication:** Required

**Body (form-data):**
- `file` (image file, required) - jpg, png, gif, webp only, max 5MB

**Example:**
```bash
curl -X POST http://localhost:8000/api/users/profile/avatar \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/avatar.jpg"
```

**Response:**
```json
{
  "success": true,
  "message": "Profile picture updated successfully",
  "data": {
    "profile_picture": "http://localhost:8000/uploads/6974a0edd85365885aac6fb4/avatar_20260126.jpg"
  }
}
```

---

### 4. Upload Cover Image

```http
POST /api/users/profile/cover
```

**Authentication:** Required

**Body (form-data):**
- `file` (image file, required) - jpg, png, gif, webp only, max 10MB

**Example:**
```bash
curl -X POST http://localhost:8000/api/users/profile/cover \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/cover.jpg"
```

**Response:**
```json
{
  "success": true,
  "message": "Cover image updated successfully",
  "data": {
    "cover_image": "http://localhost:8000/uploads/6974a0edd85365885aac6fb4/cover_20260126.jpg"
  }
}
```

---

### 5. Get User's Questions

```http
GET /api/users/{user_id}/questions?page=1&limit=20&sort_by=created_at
```

**Query Parameters:**
- `page` (int, default: 1)
- `limit` (int, default: 20, max: 100)
- `sort_by` (string, options: `created_at`, `upvote_count`, `view_count`)

**Response:**
```json
{
  "success": true,
  "message": "Questions retrieved successfully",
  "data": {
    "questions": [
      {
        "id": "69774586151dd03ac5e7df75",
        "title": "How to maintain consistent character appearance...",
        "body": "I'm creating a graphic novel...",
        "slug": "how-to-maintain-consistent-character",
        "author_id": "6974a0edd85365885aac6fb4",
        "author_name": "PromptWizard",
        "upvote_count": 452,
        "downvote_count": 2,
        "view_count": 12500,
        "reply_count": 34,
        "is_solved": true,
        "is_pinned": false,
        "is_locked": false,
        "tags": ["midjourney", "character-design"],
        "created_at": "2026-01-15T10:30:00",
        "updated_at": "2026-01-15T10:30:00"
      }
    ],
    "pagination": {
      "total": 89,
      "page": 1,
      "limit": 20,
      "total_pages": 5
    }
  }
}
```

---

### 6. Get User's Answers

```http
GET /api/users/{user_id}/answers?page=1&limit=20&sort_by=created_at
```

**Query Parameters:**
- `page` (int, default: 1)
- `limit` (int, default: 20, max: 100)
- `sort_by` (string, options: `created_at`, `upvote_count`)

**Response:**
```json
{
  "success": true,
  "message": "Answers retrieved successfully",
  "data": {
    "answers": [
      {
        "id": "69775a735eaca8adba8302ef",
        "post_id": "69774586151dd03ac5e7df75",
        "post_title": "How to maintain consistent character appearance...",
        "post_slug": "how-to-maintain-consistent-character",
        "body": "Use --cref parameter with Midjourney...",
        "author_id": "6974a0edd85365885aac6fb4",
        "author_name": "PromptWizard",
        "upvote_count": 250,
        "downvote_count": 1,
        "reply_count": 5,
        "is_accepted": true,
        "is_edited": false,
        "created_at": "2026-01-15T11:00:00",
        "updated_at": "2026-01-15T11:00:00"
      }
    ],
    "pagination": {
      "total": 1245,
      "page": 1,
      "limit": 20,
      "total_pages": 63
    }
  }
}
```

---

### 7. Get User Statistics Only

```http
GET /api/users/{user_id}/statistics
```

**Description:** Lightweight endpoint for stats without full profile.

**Response:**
```json
{
  "success": true,
  "message": "Statistics retrieved successfully",
  "data": {
    "statistics": {
      "reputation": 45230,
      "global_rank": 127,
      "accepted_answers": 971,
      "total_answers": 1245,
      "total_questions": 89,
      "total_views": 1200000,
      "impact": 1200000
    },
    "badges": {
      "gold": 15,
      "silver": 42,
      "bronze": 89
    }
  }
}
```

---

### 8. Get User's Top Tags

```http
GET /api/users/{user_id}/top-tags?limit=10
```

**Query Parameters:**
- `limit` (int, default: 10, max: 50)

**Response:**
```json
{
  "success": true,
  "message": "Top tags retrieved successfully",
  "data": {
    "top_tags": [
      {"name": "chatgpt", "count": 1245},
      {"name": "midjourney", "count": 890},
      {"name": "claude", "count": 756}
    ]
  }
}
```

---

### 9. Get User's Top Posts

```http
GET /api/users/{user_id}/top-posts?limit=4
```

**Query Parameters:**
- `limit` (int, default: 4, max: 20)

**Response:**
```json
{
  "success": true,
  "message": "Top posts retrieved successfully",
  "data": {
    "top_posts": [
      {
        "id": "69774586151dd03ac5e7df75",
        "title": "How to write a prompt...",
        "upvote_count": 452,
        "view_count": 12500,
        "reply_count": 34,
        "created_at": "2026-01-15T10:30:00",
        "is_solved": true
      }
    ]
  }
}
```

---

## 🎯 Statistics Calculation

### Reputation System

**Points earned:**
- Post upvote: **+10 points**
- Answer upvote: **+10 points**
- Accepted answer: **+15 points**

**Points lost:**
- Post downvote: **-2 points**
- Answer downvote: **-2 points**

**Minimum:** 0 (reputation cannot be negative)

---

## 🏅 Badge System

### Gold Badges (Rare Achievements)
- Reputation ≥ 50,000
- Reputation ≥ 25,000
- Reputation ≥ 10,000
- 100+ accepted answers
- 500+ accepted answers
- 1M+ total views

### Silver Badges (Notable Achievements)
- Reputation ≥ 5,000
- Reputation ≥ 2,500
- Reputation ≥ 1,000
- 50+ accepted answers
- 25+ accepted answers
- 50+ questions
- 100+ answers
- 100K+ total views

### Bronze Badges (Common Achievements)
- First question posted
- First answer posted
- Reputation ≥ 100
- Reputation ≥ 500
- First accepted answer
- 10+ accepted answers
- 10+ questions
- 10+ answers
- 50+ answers

---

## 🔧 Frontend Implementation

### Profile Page Component

```jsx
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

function UserProfilePage() {
  const { userId } = useParams();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  
  useEffect(() => {
    loadProfile();
  }, [userId]);
  
  const loadProfile = async () => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/users/${userId}/profile`
      );
      const result = await response.json();
      
      if (result.success) {
        setProfile(result.data.profile);
      }
    } catch (error) {
      console.error('Error loading profile:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) return <div>Loading...</div>;
  if (!profile) return <div>Profile not found</div>;
  
  return (
    <div className="profile-page">
      {/* Cover Image */}
      <div 
        className="profile-cover"
        style={{
          backgroundImage: profile.cover_image 
            ? `url(${profile.cover_image})` 
            : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          height: '300px',
          backgroundSize: 'cover'
        }}
      />
      
      {/* Profile Header */}
      <div className="profile-header">
        <div className="profile-avatar">
          <img 
            src={profile.profile_picture || '/default-avatar.png'} 
            alt={profile.full_name}
          />
        </div>
        
        <div className="profile-info">
          <h1>{profile.full_name || profile.username}</h1>
          
          {/* Rank Badge */}
          <div className="rank-badge">
            Grandmaster
          </div>
          
          {/* Title/Bio */}
          {profile.title && (
            <p className="profile-title">{profile.title}</p>
          )}
          
          {/* Edit Profile Button (only for own profile) */}
          {isOwnProfile && (
            <button onClick={() => setShowEditModal(true)}>
              Edit Profile
            </button>
          )}
        </div>
      </div>
      
      {/* Profile Details */}
      <div className="profile-details">
        {profile.location && (
          <div className="detail-item">
            📍 {profile.location}
          </div>
        )}
        {profile.website && (
          <div className="detail-item">
            🔗 <a href={`https://${profile.website}`} target="_blank">
              {profile.website}
            </a>
          </div>
        )}
        <div className="detail-item">
          📅 Joined {new Date(profile.joined_date).toLocaleDateString('en-US', {
            month: 'short',
            year: 'numeric'
          })}
        </div>
      </div>
      
      {/* About Me */}
      {profile.about_me && (
        <div className="about-section">
          <h3>About Me</h3>
          <p>{profile.about_me}</p>
        </div>
      )}
      
      {/* Tabs */}
      <div className="profile-tabs">
        <button 
          className={activeTab === 'overview' ? 'active' : ''}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button 
          className={activeTab === 'answers' ? 'active' : ''}
          onClick={() => setActiveTab('answers')}
        >
          Answers
        </button>
        <button 
          className={activeTab === 'questions' ? 'active' : ''}
          onClick={() => setActiveTab('questions')}
        >
          Questions
        </button>
      </div>
      
      {/* Content Area */}
      <div className="profile-content">
        {activeTab === 'overview' && (
          <OverviewTab profile={profile} />
        )}
        {activeTab === 'answers' && (
          <AnswersTab userId={userId} />
        )}
        {activeTab === 'questions' && (
          <QuestionsTab userId={userId} />
        )}
      </div>
      
      {/* Sidebar */}
      <aside className="profile-sidebar">
        {/* Statistics */}
        <div className="stats-card">
          <h3>Statistics</h3>
          <div className="stat-item">
            <div className="stat-value">{profile.statistics.reputation.toLocaleString()}</div>
            <div className="stat-label">Reputation</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">#{profile.statistics.global_rank}</div>
            <div className="stat-label">Global Rank</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{profile.statistics.accepted_answers}</div>
            <div className="stat-label">Accepted Answers</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{profile.statistics.total_questions}</div>
            <div className="stat-label">Questions</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{(profile.statistics.impact / 1000000).toFixed(1)}M</div>
            <div className="stat-label">Impact</div>
          </div>
        </div>
        
        {/* Badges */}
        <div className="badges-card">
          <h3>Badges</h3>
          <div className="badges">
            <div className="badge gold">
              🥇 {profile.badges.gold} <span>Gold</span>
            </div>
            <div className="badge silver">
              🥈 {profile.badges.silver} <span>Silver</span>
            </div>
            <div className="badge bronze">
              🥉 {profile.badges.bronze} <span>Bronze</span>
            </div>
          </div>
        </div>
        
        {/* Top Tags */}
        <div className="tags-card">
          <h3>Top Tags</h3>
          {profile.top_tags.map(tag => (
            <div key={tag.name} className="tag-item">
              <span className="tag-name">{tag.name}</span>
              <span className="tag-count">{tag.count}</span>
            </div>
          ))}
          <button className="view-all-tags">View All Tags</button>
        </div>
      </aside>
    </div>
  );
}

function OverviewTab({ profile }) {
  return (
    <div className="overview-tab">
      <h3>Top Posts</h3>
      <button className="view-all-link">View all</button>
      
      {profile.top_posts.map(post => (
        <div key={post.id} className="top-post-item">
          <div className="post-votes">{post.upvote_count} votes</div>
          <div className="post-info">
            <a href={`/questions/${post.id}`}>{post.title}</a>
            <div className="post-meta">
              {new Date(post.created_at).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
              })}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

### Edit Profile Modal

```jsx
function EditProfileModal({ profile, onClose, onSave }) {
  const [formData, setFormData] = useState({
    full_name: profile.full_name || '',
    title: profile.title || '',
    location: profile.location || '',
    website: profile.website || '',
    about_me: profile.about_me || ''
  });
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const formDataObj = new FormData();
    Object.keys(formData).forEach(key => {
      if (formData[key]) {
        formDataObj.append(key, formData[key]);
      }
    });
    
    const response = await fetch('http://localhost:8000/api/users/profile', {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: formDataObj
    });
    
    const result = await response.json();
    
    if (result.success) {
      onSave(result.data.profile);
    } else {
      alert(result.message);
    }
  };
  
  return (
    <div className="modal">
      <div className="modal-content">
        <h2>Edit Profile</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Display Name</label>
            <input
              type="text"
              value={formData.full_name}
              onChange={(e) => setFormData({...formData, full_name: e.target.value})}
              maxLength={100}
            />
          </div>
          
          <div className="form-group">
            <label>Title/Bio</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({...formData, title: e.target.value})}
              placeholder="Senior AI Prompt Engineer | Specializing in..."
              maxLength={200}
            />
          </div>
          
          <div className="form-group">
            <label>Location</label>
            <input
              type="text"
              value={formData.location}
              onChange={(e) => setFormData({...formData, location: e.target.value})}
              placeholder="San Francisco, CA"
              maxLength={100}
            />
          </div>
          
          <div className="form-group">
            <label>Website</label>
            <input
              type="text"
              value={formData.website}
              onChange={(e) => setFormData({...formData, website: e.target.value})}
              placeholder="yourwebsite.com"
              maxLength={200}
            />
          </div>
          
          <div className="form-group">
            <label>About Me</label>
            <textarea
              value={formData.about_me}
              onChange={(e) => setFormData({...formData, about_me: e.target.value})}
              rows={6}
              maxLength={5000}
            />
          </div>
          
          <div className="form-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit">Save Changes</button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

---

### Upload Avatar/Cover

```jsx
function ImageUpload({ type, currentImage, onUpdate }) {
  const [uploading, setUploading] = useState(false);
  
  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }
    
    // Validate file size (5MB for avatar, 10MB for cover)
    const maxSize = type === 'avatar' ? 5 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxSize) {
      alert(`File too large. Max size: ${maxSize / 1024 / 1024}MB`);
      return;
    }
    
    setUploading(true);
    
    const formData = new FormData();
    formData.append('file', file);
    
    const endpoint = type === 'avatar' 
      ? '/api/users/profile/avatar'
      : '/api/users/profile/cover';
    
    try {
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      });
      
      const result = await response.json();
      
      if (result.success) {
        const imageUrl = type === 'avatar' 
          ? result.data.profile_picture 
          : result.data.cover_image;
        onUpdate(imageUrl);
      } else {
        alert(result.message);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload image');
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <div className="image-upload">
      <input
        type="file"
        id={`${type}-upload`}
        accept="image/*"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
      <label htmlFor={`${type}-upload`} className="upload-button">
        {uploading ? 'Uploading...' : `Change ${type}`}
      </label>
    </div>
  );
}
```

---

## 🔄 Server Restart

After adding profile system:

```bash
# Stop server (Ctrl+C)

# Restart
uvicorn app.main:app --reload
```

---

## ✅ Testing

### Test Profile Endpoints

```bash
# 1. Get profile
curl http://localhost:8000/api/users/6974a0edd85365885aac6fb4/profile

# 2. Update profile (requires auth)
curl -X PUT http://localhost:8000/api/users/profile \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "full_name=John Doe" \
  -F "title=AI Engineer" \
  -F "location=San Francisco" \
  -F "website=example.com"

# 3. Upload avatar
curl -X POST http://localhost:8000/api/users/profile/avatar \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@avatar.jpg"

# 4. Get user's questions
curl http://localhost:8000/api/users/6974a0edd85365885aac6fb4/questions

# 5. Get user's answers
curl http://localhost:8000/api/users/6974a0edd85365885aac6fb4/answers

# 6. Get statistics
curl http://localhost:8000/api/users/6974a0edd85365885aac6fb4/statistics
```

---

## 📊 Database Schema Updates

### Users Collection (Extended)

```javascript
{
  _id: ObjectId,
  email: "user@example.com",
  full_name: "John Doe",
  hashed_password: "...",
  auth_provider: "email",
  
  // NEW PROFILE FIELDS
  username: "johndoe",
  profile_picture: "http://localhost:8000/uploads/avatar.jpg",
  cover_image: "http://localhost:8000/uploads/cover.jpg",
  title: "Senior AI Engineer",
  location: "San Francisco, CA",
  website: "example.com",
  about_me: "Passionate about AI...",
  
  // Existing fields
  is_verified: true,
  is_active: true,
  created_at: ISODate,
  updated_at: ISODate
}
```

**Note:** Profile fields are optional and calculated on-the-fly. No need to manually add them to existing users.

---

## 🎯 Features Checklist

✅ Get user profile (public)  
✅ Update own profile  
✅ Upload profile picture  
✅ Upload cover image  
✅ Get user's questions  
✅ Get user's answers  
✅ Calculate reputation  
✅ Calculate global rank  
✅ Calculate badges (gold, silver, bronze)  
✅ Get top tags  
✅ Get top posts  
✅ Statistics endpoint  

---

**Status:** ✅ Complete  
**Date:** January 26, 2026  
**Action Required:** Restart server + Test endpoints  

**Visit:** `/api/docs` for interactive API documentation!
```
