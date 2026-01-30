from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AuditAction(str, Enum):
    """Audit action types"""
    # Contest actions
    CONTEST_CREATED = "contest_created"
    CONTEST_UPDATED = "contest_updated"
    CONTEST_DELETED = "contest_deleted"
    CONTEST_STARTED = "contest_started"
    CONTEST_COMPLETED = "contest_completed"
    
    # Task actions
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_DELETED = "task_deleted"
    
    # Submission actions
    SUBMISSION_CREATED = "submission_created"
    SUBMISSION_UPDATED = "submission_updated"
    SUBMISSION_DELETED = "submission_deleted"
    SUBMISSION_REVIEWED = "submission_reviewed"
    
    # Participant actions
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    
    # Payment actions (for future)
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_REFUNDED = "payment_refunded"
    PRIZE_PAID = "prize_paid"


class AuditEntry(BaseModel):
    """Audit trail entry"""
    contest_id: str
    action: AuditAction
    user_id: str
    username: str
    entity_type: str  # "contest", "task", "submission", "participant"
    entity_id: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None  # What changed
    metadata: Optional[Dict[str, Any]] = None  # Additional info
    timestamp: datetime
    ip_address: Optional[str] = None
