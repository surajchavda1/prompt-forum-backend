from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TaskCreate(BaseModel):
    """Schema for creating a contest task"""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    points: int = Field(..., gt=0, description="Points awarded for completion")
    order: int = Field(..., ge=1, description="Task order/number")
    requirements: Optional[str] = None
    deliverables: Optional[str] = None


class TaskUpdate(BaseModel):
    """Schema for updating a task (only before contest starts)"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=20)
    points: Optional[int] = Field(None, gt=0)
    order: Optional[int] = Field(None, ge=1)
    requirements: Optional[str] = None
    deliverables: Optional[str] = None


class TaskResponse(BaseModel):
    """Schema for task response"""
    id: str
    contest_id: str
    title: str
    description: str
    points: int
    order: int
    requirements: Optional[str] = None
    deliverables: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Calculated fields
    submission_count: int = 0
    approved_count: int = 0
    user_submitted: bool = False
    user_approved: bool = False
