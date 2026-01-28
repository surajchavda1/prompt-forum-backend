from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CommentFileAttachment(BaseModel):
    """File attachment for comment schema"""
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    file_url: str
    uploaded_at: datetime


class CommentBase(BaseModel):
    """Base comment/answer schema"""
    body: str = Field(..., min_length=10, description="Comment/answer content")


class CommentCreate(CommentBase):
    """Schema for creating a comment/answer"""
    pass


class CommentUpdate(BaseModel):
    """Schema for updating a comment/answer"""
    body: Optional[str] = Field(None, min_length=10)


class CommentResponse(CommentBase):
    """Schema for comment/answer response"""
    id: str = Field(..., alias="_id")
    post_id: str
    parent_id: Optional[str] = None  # For nested replies
    author_id: str
    author_name: str
    upvote_count: int = 0
    downvote_count: int = 0
    reply_count: int = 0  # Number of replies to this comment
    is_accepted: bool = False
    is_edited: bool = False
    attachments: List[CommentFileAttachment] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class CommentListItem(BaseModel):
    """Schema for comment list item (summary)"""
    id: str
    post_id: str
    author_id: str
    author_name: str
    body: str
    upvote_count: int
    downvote_count: int
    is_accepted: bool
    is_edited: bool
    created_at: datetime
    updated_at: datetime
