from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.cache import get_cached_tasks, invalidate_user_cache, set_cached_tasks
from core.logger import logger
from core.security import get_current_admin_user, get_current_user, verify_csrf_token
from db.database import get_db
from models.models import Task, User
from schemas.schemas import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskResponse)
def post_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(verify_csrf_token),
):

    try:
        new_data = Task(
            title=task.title, priority=task.priority, user_id=current_user.id
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)

        # CLEAR CACHE: data has changed, old cache is outdated!
        invalidate_user_cache(current_user.id)

        logger.info(f"Created a new task for user {current_user.email}")
        return new_data
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.warning(f"Error creating task for user {current_user.email}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {e!s}")


@router.get("/", response_model=list[TaskResponse])
def get_tasks(
    completed: bool | None = None,
    priority: int | None = None,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Try to retrieve tasks from Redis cache (only for base request without filters and default pagination)
    if completed is None and priority is None and limit == 10 and offset == 0:
        cached_tasks = get_cached_tasks(current_user.id)
        if cached_tasks is not None:
            logger.info(
                f"⚡ Cache found for user {current_user.email} (Redis Cache Hit)"
            )
            return cached_tasks

    # If cache is missing (Cache Miss), go to PostgreSQL database
    query = db.query(Task).filter(Task.user_id == current_user.id)

    if completed is not None:
        query = query.filter(Task.completed == completed)
    if priority is not None:
        query = query.filter(Task.priority == priority)

    tasks_list = query.offset(offset).limit(limit).all()

    # Save to Redis cache if it's a standard request without filters
    if completed is None and priority is None and limit == 10 and offset == 0:
        tasks_dicts = [TaskResponse.model_validate(t).model_dump() for t in tasks_list]
        set_cached_tasks(current_user.id, tasks_dicts)
        logger.info(f"💾 Data written to cache for user {current_user.email}")

    return tasks_list


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    new_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(verify_csrf_token),
):
    updt = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )

    if not updt:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        update_data = new_data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(updt, key, value)

        db.commit()
        db.refresh(updt)

        invalidate_user_cache(current_user.id)

        return updt

    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating task: {e!s}",
        )


@router.delete("/{task_id}")
def del_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(verify_csrf_token),
):
    delet = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )

    if not delet:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        db.delete(delet)
        db.commit()

        invalidate_user_cache(current_user.id)

        return {"message": f"Task with id {task_id} successfully deleted"}

    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting: {e!s}",
        )


@router.get("/admin/tasks", response_model=list[TaskResponse])
def get_all_tasks_for_admin(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    return db.query(Task).all()
