from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TaskCreate(BaseModel):
    """Schema for creating a contest task"""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    points: int = Field(..., gt=0, le=100, description="Points awarded for completion (max 100)")
    order: int = Field(..., ge=1, description="Task order/number")
    requirements: str = Field(..., min_length=10, description="Task requirements")
    deliverables: str = Field(..., min_length=10, description="Expected deliverables")


class TaskUpdate(BaseModel):
    """Schema for updating a task (only before contest starts)"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=20)
    points: Optional[int] = Field(None, gt=0, le=100, description="Points (max 100)")
    order: Optional[int] = Field(None, ge=1)
    requirements: Optional[str] = Field(None, min_length=10)
    deliverables: Optional[str] = Field(None, min_length=10)


class TaskResponse(BaseModel):
    """Schema for task response"""
    id: str
    contest_id: str
    title: str
    description: str
    points: int  # Max 100
    order: int
    requirements: str
    deliverables: str
    created_at: datetime
    updated_at: datetime
    
    # Calculated fields
    submission_count: int = 0
    approved_count: int = 0
    user_submitted: bool = False
    user_approved: bool = False
