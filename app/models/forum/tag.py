from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TagBase(BaseModel):
    """Base tag schema"""
    name: str = Field(..., min_length=1, max_length=50)
    slug: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    subcategory_id: Optional[str] = Field(None, description="ID of the subcategory this tag belongs to")
    group: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class TagCreate(TagBase):
    """Schema for tag creation"""
    pass


class TagUpdate(BaseModel):
    """Schema for tag update"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    subcategory_id: Optional[str] = None
    group: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class TagResponse(TagBase):
    """Schema for tag response"""
    id: str = Field(..., alias="_id")
    subcategory_id: Optional[str] = None
    usage_count: int = 0
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
