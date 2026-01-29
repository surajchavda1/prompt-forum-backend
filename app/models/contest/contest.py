from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ContestStatus(str, Enum):
    """Contest status types"""
    DRAFT = "draft"  # Owner can edit
    ACTIVE = "active"  # Started, no editing, accepting submissions
    JUDGING = "judging"  # Ended, owner reviewing submissions
    COMPLETED = "completed"  # All submissions judged, winners announced


class ContestDifficulty(str, Enum):
    """Contest difficulty levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ContestType(str, Enum):
    """Contest type"""
    INDIVIDUAL = "individual"
    TEAM = "team"


class ContestCreate(BaseModel):
    """Schema for creating a contest"""
    title: str = Field(..., min_length=10, max_length=200)
    description: str = Field(..., min_length=50)
    category: str = Field(..., description="Contest category")
    difficulty: ContestDifficulty
    contest_type: ContestType = ContestType.INDIVIDUAL
    total_prize: float = Field(..., gt=0)
    max_participants: int = Field(..., gt=0)
    start_date: datetime
    end_date: datetime
    rules: Optional[str] = None


class ContestUpdate(BaseModel):
    """Schema for updating a contest (only allowed in DRAFT status)"""
    title: Optional[str] = Field(None, min_length=10, max_length=200)
    description: Optional[str] = Field(None, min_length=50)
    category: Optional[str] = None
    difficulty: Optional[ContestDifficulty] = None
    contest_type: Optional[ContestType] = None
    total_prize: Optional[float] = Field(None, gt=0)
    max_participants: Optional[int] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    rules: Optional[str] = None


class ContestResponse(BaseModel):
    """Schema for contest response"""
    id: str
    title: str
    description: str
    category: str
    difficulty: ContestDifficulty
    contest_type: ContestType
    status: ContestStatus
    owner_id: str
    owner_name: str
    total_prize: float
    max_participants: int
    current_participants: int
    task_count: int
    start_date: datetime
    end_date: datetime
    cover_image: Optional[str] = None
    rules: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Calculated fields
    time_remaining: Optional[str] = None
    time_until_start: Optional[str] = None
    fill_percentage: float = 0.0
    is_joined: bool = False
    is_owner: bool = False
    can_edit: bool = False
    can_delete: bool = False
    submission_count: int = 0
