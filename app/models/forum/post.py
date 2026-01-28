from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class FileAttachment(BaseModel):
    """File attachment schema"""
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    file_url: str
    uploaded_at: datetime


class PostBase(BaseModel):
    """Base post schema"""
    title: str = Field(..., min_length=5, max_length=200)
    category_id: str = Field(..., description="Parent category ID")
    subcategory_id: Optional[str] = Field(None, description="Subcategory ID")
    tags: List[str] = Field(default=[], max_items=10, description="List of tag names or IDs")
    body: str = Field(..., min_length=20, description="Post content")


class PostCreate(PostBase):
    """Schema for creating a post"""
    pass


class PostUpdate(BaseModel):
    """Schema for updating a post"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    tags: Optional[List[str]] = Field(None, max_items=10)
    body: Optional[str] = Field(None, min_length=20)


class PostResponse(PostBase):
    """Schema for post response"""
    id: str = Field(..., alias="_id")
    author_id: str
    author_name: str
    slug: str
    view_count: int = 0
    reply_count: int = 0
    upvote_count: int = 0
    downvote_count: int = 0
    is_pinned: bool = False
    is_locked: bool = False
    is_solved: bool = False
    attachments: List[FileAttachment] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class PostListItem(BaseModel):
    """Schema for post list item (summary)"""
    id: str
    title: str
    slug: str
    author_id: str
    author_name: str
    category_id: str
    subcategory_id: Optional[str]
    tags: List[str]
    view_count: int
    reply_count: int
    upvote_count: int
    is_pinned: bool
    is_solved: bool
    created_at: datetime
    updated_at: datetime
