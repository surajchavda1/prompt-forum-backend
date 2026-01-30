from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId
from app.models.contest.audit import AuditAction


class AuditService:
    """Service for audit trail logging"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.audit_log = db.contest_audit_log
    
    async def log_action(
        self,
        contest_id: str,
        action: AuditAction,
        user_id: str,
        username: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """Log an audit trail entry"""
        try:
            audit_entry = {
                "contest_id": contest_id,
                "action": action,
                "user_id": user_id,
                "username": username,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "changes": changes,
                "metadata": metadata,
                "timestamp": datetime.utcnow(),
                "ip_address": ip_address
            }
            
            await self.audit_log.insert_one(audit_entry)
            return True
            
        except Exception as e:
            print(f"Error logging audit: {str(e)}")
            return False
    
    async def get_contest_history(
        self,
        contest_id: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get audit history for a contest"""
        try:
            history = await self.audit_log.find({
                "contest_id": contest_id
            }).sort("timestamp", -1).limit(limit).to_list(length=limit)
            
            return history
            
        except Exception as e:
            print(f"Error getting audit history: {str(e)}")
            return []
    
    async def get_user_actions(
        self,
        user_id: str,
        contest_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get actions by a user"""
        try:
            query = {"user_id": user_id}
            if contest_id:
                query["contest_id"] = contest_id
            
            actions = await self.audit_log.find(query).sort(
                "timestamp", -1
            ).limit(limit).to_list(length=limit)
            
            return actions
            
        except Exception as e:
            print(f"Error getting user actions: {str(e)}")
            return []
    
    async def get_submission_history(
        self,
        submission_id: str
    ) -> List[Dict]:
        """Get complete history of a submission"""
        try:
            history = await self.audit_log.find({
                "entity_type": "submission",
                "entity_id": submission_id
            }).sort("timestamp", 1).to_list(length=None)
            
            return history
            
        except Exception as e:
            print(f"Error getting submission history: {str(e)}")
            return []
