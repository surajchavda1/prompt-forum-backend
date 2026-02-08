from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ContestStatus(str, Enum):
    """
    Contest status types - State Machine
    
    State Transitions:
    - DRAFT -> UPCOMING (owner publishes)
    - DRAFT -> CANCELLED (owner cancels, no participants)
    - UPCOMING -> ACTIVE (auto at start_date)
    - UPCOMING -> CANCELLED (owner cancels, no participants)
    - ACTIVE -> JUDGING (end_date passed)
    - ACTIVE -> COMPLETED (owner completes or system auto-completes)
    - JUDGING -> COMPLETED (owner completes or system auto-completes)
    """
    DRAFT = "draft"  # Owner can edit, not visible to public
    UPCOMING = "upcoming"  # Published, visible to public, waiting for start_date
    ACTIVE = "active"  # Started, accepting submissions
    JUDGING = "judging"  # Ended, owner reviewing submissions
    COMPLETED = "completed"  # All submissions judged, prizes distributed
    CANCELLED = "cancelled"  # Contest cancelled (only before participants join)


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
    category_id: str = Field(..., description="Main category ID")
    subcategory_id: Optional[str] = Field(None, description="Subcategory ID")
    tags: List[str] = Field(default=[], description="List of tag slugs (must be valid for selected subcategory)")
    # Legacy field for backward compatibility
    category: Optional[str] = Field(None, description="Legacy category field - use category_id instead")
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
    category_id: Optional[str] = Field(None, description="Main category ID")
    subcategory_id: Optional[str] = Field(None, description="Subcategory ID")
    tags: Optional[List[str]] = Field(None, description="List of tag slugs")
    # Legacy field for backward compatibility
    category: Optional[str] = Field(None, description="Legacy category field - use category_id instead")
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
    category_id: str
    subcategory_id: Optional[str] = None
    tags: List[str] = []
    # Legacy field for backward compatibility
    category: Optional[str] = None
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
    
    # Visibility & Lifecycle fields
    is_active: bool = False  # Public visibility flag
    published_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    auto_completed: bool = False  # True if system completed, False if owner
    grace_period_hours: int = 24  # Hours after end_date for auto-complete
    
    # Calculated fields
    time_remaining: Optional[str] = None
    time_until_start: Optional[str] = None
    fill_percentage: float = 0.0
    is_joined: bool = False
    is_owner: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_publish: bool = False
    can_cancel: bool = False
    can_complete: bool = False
    submission_count: int = 0


class ContestInDB(BaseModel):
    """Schema for contest stored in database"""
    title: str
    slug: str
    description: str
    category_id: str
    subcategory_id: Optional[str] = None
    tags: List[str] = []
    # Legacy field for backward compatibility
    category: Optional[str] = None
    difficulty: ContestDifficulty
    contest_type: ContestType = ContestType.INDIVIDUAL
    status: ContestStatus = ContestStatus.DRAFT
    owner_id: str
    owner_name: str
    total_prize: float
    max_participants: int
    start_date: datetime
    end_date: datetime
    cover_image: Optional[str] = None
    rules: Optional[str] = None
    
    # Visibility & Lifecycle
    is_active: bool = False  # Public visibility flag
    published_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    auto_completed: bool = False
    grace_period_hours: int = 24
    
    # Payment tracking
    prize_pool_locked: bool = False
    platform_fee: float = 0.0
    total_charged: float = 0.0
    
    # Voting
    view_count: int = 0
    upvote_count: int = 0
    downvote_count: int = 0
    upvoters: List[str] = []
    downvoters: List[str] = []
    
    # Timestamps
    created_at: datetime
    updated_at: datetime


class ParticipantInDB(BaseModel):
    """Schema for participant stored in database"""
    contest_id: str
    user_id: str
    username: str
    joined_at: datetime
    
    # Simple scoring (sum of approved task points)
    total_score: int = 0
    approved_tasks: int = 0
    pending_tasks: int = 0
    
    # Weighted scoring (for prize distribution)
    weighted_score: float = 0.0
    task_scores: List[Dict[str, Any]] = []  # [{task_id, score, weightage, weighted_score}]
    
    # Earnings
    earnings: float = 0.0
    prize_distributed: bool = False
    prize_distributed_at: Optional[datetime] = None
    
    # Entry fee tracking
    entry_fee_paid: float = 0.0
    entry_fee_transaction_id: Optional[str] = None
