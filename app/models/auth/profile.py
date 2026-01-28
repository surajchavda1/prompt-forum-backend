from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime


class Badge(BaseModel):
    """User badge schema"""
    gold: int = 0
    silver: int = 0
    bronze: int = 0


class TopTag(BaseModel):
    """Top tag with count"""
    name: str
    count: int
    tag_id: Optional[str] = None


class UserStatistics(BaseModel):
    """User statistics schema"""
    reputation: int = 0
    global_rank: Optional[int] = None
    accepted_answers: int = 0
    total_answers: int = 0
    total_questions: int = 0
    total_views: int = 0
    impact: int = 0  # Total views on user's questions


class ProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, max_length=200, description="Professional title/bio")
    location: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=200)
    about_me: Optional[str] = Field(None, max_length=5000, description="About me section")


class TopPost(BaseModel):
    """Top post summary"""
    id: str
    title: str
    upvote_count: int
    view_count: int
    reply_count: int
    created_at: datetime
    is_solved: bool = False


class UserProfileResponse(BaseModel):
    """Complete user profile response"""
    # Basic info
    id: str
    email: str
    full_name: Optional[str] = None
    username: Optional[str] = None
    
    # Profile details
    profile_picture: Optional[str] = None
    cover_image: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    about_me: Optional[str] = None
    
    # Account info
    is_verified: bool
    joined_date: datetime
    
    # Statistics
    statistics: UserStatistics
    
    # Badges
    badges: Badge
    
    # Top tags
    top_tags: List[TopTag] = []
    
    # Top posts
    top_posts: List[TopPost] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "email": "promptwizard@example.com",
                "full_name": "PromptWizard",
                "username": "promptwizard",
                "profile_picture": "http://localhost:8000/uploads/avatar.jpg",
                "cover_image": "http://localhost:8000/uploads/cover.jpg",
                "title": "Senior AI Prompt Engineer | Specializing in ChatGPT & Claude",
                "location": "San Francisco, CA",
                "website": "promptwizard.dev",
                "about_me": "Passionate about bridging the gap between human intent and AI execution.",
                "is_verified": True,
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
                    {"name": "midjourney", "count": 890}
                ],
                "top_posts": []
            }
        }


class UserListItem(BaseModel):
    """User list item for leaderboards/search"""
    id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    title: Optional[str] = None
    reputation: int = 0
    badges: Badge
    joined_date: datetime


class ActivityItem(BaseModel):
    """User activity item"""
    type: str  # "question", "answer", "comment", "vote"
    title: str
    post_id: str
    created_at: datetime
    upvote_count: int = 0
