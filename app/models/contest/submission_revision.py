"""Models for submission revision system"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RevisionCreate(BaseModel):
    """Schema for creating a revision"""
    content: str = Field(..., min_length=20, description="Updated solution/proof description")
    proof_url: Optional[str] = None
    revision_note: Optional[str] = Field(None, description="What did you change?")


class RevisionResponse(BaseModel):
    """Schema for revision in history"""
    id: str
    submission_id: str
    version: int
    content: str
    proof_url: Optional[str] = None
    attachments: List[dict] = []
    
    # Review data for this version
    status: str
    feedback: Optional[str] = None
    score: Optional[int] = None
    
    # Who reviewed
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    
    # Timestamps
    submitted_at: datetime
    
    class Config:
        from_attributes = True
