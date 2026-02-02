from fastapi import APIRouter, Depends, Form, Query
from typing import Optional
from datetime import datetime
from app.database import Database
from app.services.contest.task import TaskService
from app.services.contest.contest import ContestService
from app.routes.auth.dependencies import get_current_user
from app.models.contest.task import TaskCreate, TaskUpdate
from app.utils.response import success_response, error_response, validation_error_response

router = APIRouter(prefix="/contests", tags=["Contest Tasks"])


def convert_task_to_json(task: dict) -> dict:
    """Convert task document to JSON"""
    task["id"] = str(task["_id"])
    del task["_id"]
    
    for field in ["created_at", "updated_at"]:
        if task.get(field):
            task[field] = task[field].isoformat()
    
    return task


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


@router.post("/{contest_identifier}/tasks/create")
async def create_task(
    contest_identifier: str,
    title: str = Form(..., min_length=5, max_length=200),
    description: str = Form(..., min_length=20),
    points: int = Form(..., gt=0),
    order: int = Form(..., ge=1),
    requirements: Optional[str] = Form(None),
    deliverables: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a task for a contest.
    
    - Accepts contest ID or slug
    - Only contest owner can add tasks
    - Only allowed in DRAFT status
    - Cannot add tasks after contest starts
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    task_service = TaskService(db)
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    task_data = TaskCreate(
        title=title,
        description=description,
        points=points,
        order=order,
        requirements=requirements,
        deliverables=deliverables
    )
    
    success, message, task = await task_service.create_task(
        contest_id=contest_id,
        task_data=task_data,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"task": convert_task_to_json(task)},
        status_code=201
    )


@router.get("/{contest_identifier}/tasks")
async def get_contest_tasks(
    contest_identifier: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get all tasks for a contest.
    
    - Accepts contest ID or slug
    - Public endpoint
    - Shows submission counts
    - Shows user's submission status if authenticated
    """
    db = Database.get_db()
    task_service = TaskService(db)
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    user_id = str(current_user["_id"]) if current_user else None
    
    tasks = await task_service.get_contest_tasks(
        contest_id=contest_id,
        user_id=user_id
    )
    
    tasks_data = [convert_task_to_json(t) for t in tasks]
    
    return success_response(
        message="Tasks retrieved successfully",
        data={
            "tasks": tasks_data,
            "total": len(tasks_data)
        }
    )


@router.get("/{contest_identifier}/tasks/{task_id}")
async def get_task(
    contest_identifier: str,
    task_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get single task details (accepts contest ID or slug)"""
    db = Database.get_db()
    task_service = TaskService(db)
    
    # Resolve contest identifier to ID
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    user_id = str(current_user["_id"]) if current_user else None
    
    task = await task_service.get_task_by_id(task_id, user_id)
    
    if not task:
        return error_response(
            message="Task not found",
            status_code=404
        )
    
    # Verify task belongs to contest
    if task["contest_id"] != contest_id:
        return error_response(
            message="Task doesn't belong to this contest",
            status_code=400
        )
    
    return success_response(
        message="Task retrieved successfully",
        data={"task": convert_task_to_json(task)}
    )


@router.put("/{contest_identifier}/tasks/{task_id}")
async def update_task(
    contest_identifier: str,
    task_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    points: Optional[int] = Form(None),
    order: Optional[int] = Form(None),
    requirements: Optional[str] = Form(None),
    deliverables: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a task (accepts contest ID or slug).
    
    - Only contest owner
    - Only in DRAFT status
    - Cannot edit after contest starts
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    task_service = TaskService(db)
    
    # Resolve contest identifier (validation only, task_id is used for update)
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    update_data = TaskUpdate(
        title=title,
        description=description,
        points=points,
        order=order,
        requirements=requirements,
        deliverables=deliverables
    )
    
    success, message = await task_service.update_task(
        task_id=task_id,
        update_data=update_data,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"updated": True}
    )


@router.delete("/{contest_identifier}/tasks/{task_id}")
async def delete_task(
    contest_identifier: str,
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a task (accepts contest ID or slug).
    
    - Only contest owner
    - Only in DRAFT status
    - Cannot delete if has submissions
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    db = Database.get_db()
    task_service = TaskService(db)
    
    # Resolve contest identifier (validation only)
    contest_id = await resolve_contest_id(contest_identifier, db)
    if not contest_id:
        return error_response(message="Contest not found", status_code=404)
    
    success, message = await task_service.delete_task(
        task_id=task_id,
        user_id=str(current_user["_id"])
    )
    
    if not success:
        return error_response(message=message, status_code=400)
    
    return success_response(
        message=message,
        data={"deleted": True}
    )
