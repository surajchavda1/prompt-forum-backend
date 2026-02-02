from fastapi import APIRouter, Depends, File, UploadFile, Form, Query
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from app.database import Database
from app.services.contest.submission import SubmissionService
from app.services.contest.contest import ContestService
from app.routes.auth.dependencies import get_current_user
from app.models.contest.submission import (
    SubmissionCreate,
    SubmissionUpdate,
    SubmissionReview,
    SubmissionStatus
)
from app.utils.response import success_response, error_response, validation_error_response
from app.utils.file_upload import FileUploadService, MAX_FILES_PER_UPLOAD

# Two routers: one for contest-specific submission endpoints, one for generic submission operations
contest_router = APIRouter(prefix="/contests", tags=["Contest Submissions"])
submission_router = APIRouter(prefix="/submissions", tags=["Submissions"])


async def resolve_contest_id(identifier: str, db) -> Optional[str]:
    """
    Resolve contest identifier to actual contest_id.
    Accepts both ObjectId and slug.
    """
    is_object_id = len(identifier) == 24 and all(c in '0123456789abcdef' for c in identifier.lower())
    
    if is_object_id:
        return identifier
    else:
        # Look up by slug
        contest_service = ContestService(db)
        contest = await contest_service.get_contest_by_slug(identifier)
        if contest:
            return str(contest["_id"])
        return None


def convert_submission_to_json(submission: dict) -> dict:
    """Convert submission document to JSON"""
    submission["id"] = str(submission["_id"])
    del submission["_id"]
    
    # Convert all datetime fields (including new revision system fields)
    for field in ["submitted_at", "reviewed_at", "updated_at", "first_submitted_at", "approved_at"]:
        if submission.get(field):
            if isinstance(submission[field], datetime):
                submission[field] = submission[field].isoformat()
    
    # Convert attachment dates
    for attachment in submission.get("attachments", []):
        if attachment.get("uploaded_at"):
            if isinstance(attachment["uploaded_at"], datetime):
                attachment["uploaded_at"] = attachment["uploaded_at"].isoformat()
    
    return submission


@contest_router.post("/{contest_identifier}/tasks/{task_id}/submit")
async def submit_task(
    contest_identifier: str,
    task_id: str,
    content: str = Form(..., min_length=20),
    proof_url: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user)
):
    """
    Submit solution/proof for a task (accepts contest ID or slug).
    
    - Must be participant
    - Contest must be active
    - Can attach files as proof
    - Cannot submit to own contest
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    # Handle file uploads
    attachments = []
    if files and files[0].filename:
        if len(files) > MAX_FILES_PER_UPLOAD:
            return validation_error_response(
                errors={"files": f"Maximum {MAX_FILES_PER_UPLOAD} files allowed"}
            )
        
        file_service = FileUploadService()
        user_id = str(current_user["_id"])
        
        for uploaded_file in files:
            try:
                file_info = await file_service.save_file(uploaded_file, user_id)
                attachments.append(file_info)
            except ValueError as e:
                # Clean up already uploaded files
                for att in attachments:
                    await file_service.delete_file(att["filename"], user_id)
                return validation_error_response(errors={"files": str(e)})
    
    # Create submission
    submission_service = SubmissionService(db)
    
    submission_data = SubmissionCreate(
        content=content,
        proof_url=proof_url
    )
    
    success, message, submission = await submission_service.create_submission(
        contest_id=contest_id,
        task_id=task_id,
        user_id=str(current_user["_id"]),
        username=current_user.get("username") or current_user.get("full_name") or current_user.get("email"),
        submission_data=submission_data,
        attachments=attachments
    )
    
    if not success:
        # Clean up uploaded files on error
        file_service = FileUploadService()
        for att in attachments:
            await file_service.delete_file(att["filename"], str(current_user["_id"]))
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"submission": convert_submission_to_json(submission)},
        status_code=201
    )


@contest_router.get("/{contest_identifier}/tasks/{task_id}/submissions")
async def get_task_submissions(
    contest_identifier: str,
    task_id: str,
    status: Optional[SubmissionStatus] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get all submissions for a task (accepts contest ID or slug).
    
    - Contest owner sees all submissions
    - Participants see only their own
    - Public users see approved submissions only
    """
    db = Database.get_db()
    submission_service = SubmissionService(db)
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    # Get contest
    contest = await db.contests.find_one({"_id": ObjectId(contest_id)})
    
    if not contest:
        return error_response(
            message="Contest not found",
            status_code=404
        )
    
    user_id = str(current_user["_id"]) if current_user else None
    is_owner = str(contest["owner_id"]) == user_id if user_id else False
    
    # If owner, show all submissions
    # If participant, show only their own
    # If public, show only approved
    if is_owner:
        submissions, total = await submission_service.get_submissions_by_task(
            task_id=task_id,
            status=status,
            page=page,
            limit=limit
        )
    elif user_id:
        # Show user's own submissions
        all_submissions = await submission_service.get_user_submissions(contest_id, user_id)
        submissions = [s for s in all_submissions if s["task_id"] == task_id]
        total = len(submissions)
    else:
        # Public - show only approved
        submissions, total = await submission_service.get_submissions_by_task(
            task_id=task_id,
            status=SubmissionStatus.APPROVED,
            page=page,
            limit=limit
        )
    
    submissions_data = [convert_submission_to_json(s) for s in submissions]
    
    return success_response(
        message="Submissions retrieved successfully",
        data={
            "submissions": submissions_data,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@contest_router.get("/{contest_identifier}/my-submissions")
async def get_my_submissions(
    contest_identifier: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all submissions by current user for a contest (accepts contest ID or slug).
    
    - Shows all tasks user has submitted
    - Shows approval status
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    submission_service = SubmissionService(db)
    
    submissions = await submission_service.get_user_submissions(
        contest_id=contest_id,
        user_id=str(current_user["_id"])
    )
    
    submissions_data = [convert_submission_to_json(s) for s in submissions]
    
    return success_response(
        message="Your submissions retrieved successfully",
        data={
            "submissions": submissions_data,
            "total": len(submissions_data)
        }
    )


@contest_router.get("/{contest_identifier}/submissions")
async def get_contest_submissions(
    contest_identifier: str,
    status: Optional[SubmissionStatus] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all submissions for a contest (owner only, accepts contest ID or slug).
    
    - Only contest owner can view all submissions
    - Filter by status
    - Includes task information
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    # Verify ownership
    contest = await db.contests.find_one({"_id": ObjectId(contest_id)})
    
    if not contest:
        return error_response(
            message="Contest not found",
            status_code=404
        )
    
    if str(contest["owner_id"]) != str(current_user["_id"]):
        return error_response(
            message="Only contest owner can view all submissions",
            status_code=403
        )
    
    submission_service = SubmissionService(db)
    
    submissions, total = await submission_service.get_contest_all_submissions(
        contest_id=contest_id,
        status=status,
        page=page,
        limit=limit
    )
    
    submissions_data = [convert_submission_to_json(s) for s in submissions]
    
    return success_response(
        message="Submissions retrieved successfully",
        data={
            "submissions": submissions_data,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    )


@submission_router.get("/{submission_id}")
async def get_submission(
    submission_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get a single submission by ID.
    
    - Owner can view any submission
    - Participant can only view own submissions
    - Shows all details including feedback and attachments
    """
    db = Database.get_db()
    submission_service = SubmissionService(db)
    
    # Get submission
    submission = await submission_service.get_submission_by_id(submission_id)
    
    if not submission:
        return error_response(
            message="Submission not found",
            status_code=404
        )
    
    # Get contest to check ownership
    contest = await db.contests.find_one({"_id": ObjectId(submission["contest_id"])})
    
    if not contest:
        return error_response(
            message="Contest not found",
            status_code=404
        )
    
    # Check permissions
    user_id = str(current_user["_id"]) if current_user else None
    is_owner = str(contest.get("owner_id")) == user_id if user_id else False
    is_participant = str(submission["user_id"]) == user_id if user_id else False
    
    # Only owner or participant can view
    if not is_owner and not is_participant:
        return error_response(
            message="You don't have permission to view this submission",
            status_code=403
        )
    
    # Add permissions
    submission["is_owner"] = is_participant
    submission["can_edit"] = is_participant and submission["status"] in ["pending", "revision_requested"]
    submission["can_delete"] = is_participant and submission["status"] == "pending"
    
    return success_response(
        message="Submission retrieved successfully",
        data={"submission": convert_submission_to_json(submission)}
    )


@submission_router.put("/{submission_id}")
async def update_submission(
    submission_id: str,
    content: Optional[str] = Form(None),
    proof_url: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a submission.
    
    - Only own submission
    - Only if pending or revision requested
    - Resets status to pending after edit
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    submission_service = SubmissionService(db)
    
    update_data = SubmissionUpdate(
        content=content,
        proof_url=proof_url
    )
    
    success, message = await submission_service.update_submission(
        submission_id=submission_id,
        update_data=update_data,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"updated": True}
    )


@submission_router.delete("/{submission_id}")
async def delete_submission(
    submission_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a submission.
    
    - Only own submission
    - Only if pending status
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    submission_service = SubmissionService(db)
    
    success, message = await submission_service.delete_submission(
        submission_id=submission_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"deleted": True}
    )


@submission_router.post("/{submission_id}/revise")
async def submit_revision(
    submission_id: str,
    content: str = Form(..., min_length=20),
    proof_url: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a revision after owner requests changes.
    
    SECURITY:
    - Only if status = revision_requested
    - Only by submission owner
    - Saves old version to history
    - Increments version number
    - Resets status to pending
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    # Handle file uploads
    attachments = []
    if files:
        try:
            file_service = FileUploadService()
            user_id = str(current_user["_id"])
            
            if len(files) > MAX_FILES_PER_UPLOAD:
                return validation_error_response(
                    errors={"files": f"Maximum {MAX_FILES_PER_UPLOAD} files allowed"}
                )
            
            for file in files:
                if file.filename:
                    file_info = await file_service.save_file(file, user_id)
                    attachments.append(file_info)
                    
        except ValueError as e:
            return validation_error_response(errors={"files": str(e)})
    
    db = Database.get_db()
    submission_service = SubmissionService(db)
    
    success, message, updated_submission = await submission_service.submit_revision(
        submission_id=submission_id,
        content=content,
        proof_url=proof_url,
        attachments=attachments,
        user_id=str(current_user["_id"]),
        username=current_user.get("username") or current_user.get("full_name") or current_user.get("email")
    )
    
    if not success:
        return error_response(message=message, status_code=403 if "not allowed" in message.lower() else 400)
    
    return success_response(
        message=message,
        data={"submission": convert_submission_to_json(updated_submission)}
    )


@submission_router.get("/{submission_id}/history")
async def get_submission_history(
    submission_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get full revision history for a submission.
    
    - Owner can view any submission history
    - Participant can only view own submission history
    - Shows all versions in timeline format
    """
    db = Database.get_db()
    submission_service = SubmissionService(db)
    
    # Get submission and history
    submission, revisions = await submission_service.get_submission_history(submission_id)
    
    if not submission:
        return error_response(
            message="Submission not found",
            status_code=404
        )
    
    # Get contest to check permissions
    contest = await db.contests.find_one({"_id": ObjectId(submission["contest_id"])})
    
    if not contest:
        return error_response(
            message="Contest not found",
            status_code=404
        )
    
    # Check permissions
    user_id = str(current_user["_id"]) if current_user else None
    is_owner = str(contest.get("owner_id")) == user_id if user_id else False
    is_participant = str(submission["user_id"]) == user_id if user_id else False
    
    # Only owner or participant can view history
    if not is_owner and not is_participant:
        return error_response(
            message="You don't have permission to view this submission history",
            status_code=403
        )
    
    # Convert revisions
    revisions_data = []
    for rev in revisions:
        rev["id"] = str(rev["_id"])
        del rev["_id"]
        
        # Convert dates
        for field in ["reviewed_at", "submitted_at", "created_at"]:
            if rev.get(field):
                rev[field] = rev[field].isoformat()
        
        revisions_data.append(rev)
    
    return success_response(
        message="Submission history retrieved successfully",
        data={
            "submission": convert_submission_to_json(submission),
            "revisions": revisions_data,
            "total_versions": len(revisions_data) + 1
        }
    )


@submission_router.post("/{submission_id}/review")
async def review_submission(
    submission_id: str,
    status: SubmissionStatus = Form(...),
    feedback: Optional[str] = Form(None),
    score: Optional[int] = Form(None, ge=0, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Review a submission (approve/reject/request revision).
    
    SECURITY:
    - Only contest owner
    - Cannot review locked submissions
    - Approved/rejected = locked forever
    - Revision requested = allows user to revise
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    submission_service = SubmissionService(db)
    
    review_data = SubmissionReview(
        status=status,
        feedback=feedback,
        score=score
    )
    
    success, message = await submission_service.review_submission(
        submission_id=submission_id,
        review_data=review_data,
        reviewer_id=str(current_user["_id"]),
        reviewer_name=current_user.get("full_name") or current_user.get("email")
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"reviewed": True, "status": status}
    )
