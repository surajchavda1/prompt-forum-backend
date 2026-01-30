from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SubmissionStatus(str, Enum):
    """Submission status"""
    PENDING = "pending"  # Waiting for owner review
    APPROVED = "approved"  # Approved by owner
    REJECTED = "rejected"  # Rejected by owner
    REVISION_REQUESTED = "revision_requested"  # Owner requested changes


class SubmissionCreate(BaseModel):
    """Schema for creating a submission"""
    content: str = Field(..., min_length=20, description="Solution/proof description")
    proof_url: Optional[str] = None


class SubmissionUpdate(BaseModel):
    """Schema for updating submission (only if pending or revision requested)"""
    content: Optional[str] = Field(None, min_length=20)
    proof_url: Optional[str] = None


class SubmissionReview(BaseModel):
    """Schema for owner reviewing a submission"""
    status: SubmissionStatus = Field(..., description="approved, rejected, or revision_requested")
    feedback: Optional[str] = None
    score: Optional[int] = Field(None, ge=0, le=100, description="Score out of 100")


class SubmissionResponse(BaseModel):
    """Schema for submission response"""
    id: str
    contest_id: str
    task_id: str
    user_id: str
    username: str
    content: str
    proof_url: Optional[str] = None
    attachments: List[dict] = []
    status: SubmissionStatus
    score: Optional[int] = None
    feedback: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    updated_at: datetime
    
    # NEW: Revision system fields
    version: int = 1
    is_locked: bool = False
    can_revise: bool = False
    revision_count: int = 0
    first_submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    
    # Calculated fields
    is_owner: bool = False
    can_edit: bool = False
    can_delete: bool = False


class SubmissionListItem(BaseModel):
    """Simplified submission for listings"""
    id: str
    user_id: str
    username: str
    task_id: str
    task_title: str
    status: SubmissionStatus
    score: Optional[int] = None
    submitted_at: datetime
