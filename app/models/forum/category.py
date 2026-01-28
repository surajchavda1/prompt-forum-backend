from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CategoryBase(BaseModel):
    """Base category schema"""
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[str] = None
    icon: Optional[str] = None
    order: int = 0


class CategoryCreate(CategoryBase):
    """Schema for category creation"""
    pass


class CategoryUpdate(BaseModel):
    """Schema for category update"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = None
    order: Optional[int] = None


class CategoryResponse(CategoryBase):
    """Schema for category response"""
    id: str = Field(..., alias="_id")
    post_count: int = 0
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class CategoryWithSubcategories(CategoryResponse):
    """Category with its subcategories"""
    subcategories: List[CategoryResponse] = []
