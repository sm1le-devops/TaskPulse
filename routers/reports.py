import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from core.security import get_current_user
from models.models import User
from workers.celery_app import celery
from workers.celery_tasks import generate_user_report_task

router = APIRouter(prefix="/reports", tags=["Reports & Celery"])

IDEMPOTENCY_TTL = 60 * 60


@router.post("/generate")
async def trigger_report(
    request: Request,
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    """
    Starts a background report generation task.

    Idempotency-Key prevents duplicate Celery tasks
    when the same request is submitted multiple times.
    """

    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    redis_client = request.app.state.redis

    redis_key = f"idempotency:reports:generate:{current_user.id}:{idempotency_key}"

    task_id = str(uuid.uuid4())

    created = await redis_client.set(
        redis_key,
        task_id,
        nx=True,
        ex=IDEMPOTENCY_TTL,
    )

    if not created:
        existing_task_id = await redis_client.get(redis_key)

        if not existing_task_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key is being processed. Please retry.",
            )

        return {
            "task_id": existing_task_id,
            "status": "PENDING",
            "ready": False,
            "result": None,
            "idempotent": True,
        }

    try:
        generate_user_report_task.apply_async(
            args=[current_user.email],
            task_id=task_id,
        )

    except Exception:  # noqa: BLE001
        await redis_client.delete(redis_key)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to start report generation",
        )

    return {
        "task_id": task_id,
        "status": "PENDING",
        "ready": False,
        "result": None,
        "idempotent": False,
    }


@router.get("/status/{task_id}")
def get_report_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Checks the task status and returns the result if ready."""

    task_result = AsyncResult(task_id, app=celery)

    return {
        "task_id": task_id,
        "status": task_result.status,
        "ready": task_result.ready(),
        "result": task_result.result if task_result.ready() else None,
    }


@router.post("/cancel/{task_id}")
async def cancel_report_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel a running or pending Celery task."""

    task_result = AsyncResult(task_id, app=celery)

    task_result.revoke(
        terminate=True,
        signal="SIGKILL",
    )

    return {
        "status": "success",
        "message": f"Task {task_id} successfully cancelled",
        "task_id": task_id,
        "current_task_status": task_result.status,
    }
