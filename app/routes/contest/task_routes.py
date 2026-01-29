from fastapi import APIRouter, Depends, Form, Query
from typing import Optional
from datetime import datetime
from app.database import Database
from app.services.contest.task import TaskService
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


@router.post("/{contest_id}/tasks/create")
async def create_task(
    contest_id: str,
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


@router.get("/{contest_id}/tasks")
async def get_contest_tasks(
    contest_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get all tasks for a contest.
    
    - Public endpoint
    - Shows submission counts
    - Shows user's submission status if authenticated
    """
    db = Database.get_db()
    task_service = TaskService(db)
    
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


@router.get("/{contest_id}/tasks/{task_id}")
async def get_task(
    contest_id: str,
    task_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get single task details"""
    db = Database.get_db()
    task_service = TaskService(db)
    
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


@router.put("/{contest_id}/tasks/{task_id}")
async def update_task(
    contest_id: str,
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
    Update a task.
    
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


@router.delete("/{contest_id}/tasks/{task_id}")
async def delete_task(
    contest_id: str,
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a task.
    
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
