from celery.result import AsyncResult
from workers.celery_app import celery
from workers.celery_tasks import generate_user_report_task
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models.models import User
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from workers.celery_app import celery
from core.security import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports & Celery"])


@router.post("/generate")
def trigger_report(current_user: User = Depends(get_current_user)):
  """**Starts a background task to generate a report for the current user.**"""
  # Start the task via Celery, passing the current authorized user's email
  task = generate_user_report_task.delay(current_user.email)
    
    
  return {"task_id": task.id, "status": "PENDING", "ready": False, "result": None}


@router.get("/status/{task_id}")
def get_report_status(
    task_id: str, current_user: User = Depends(get_current_user)
):
  """Checks the task status in Redis and returns the result if ready"""
  task_result = AsyncResult(task_id, app=celery)

  response = {
      "task_id": task_id,
      "status": task_result.status,  
      "ready": task_result.ready(),  
      "result": (
          task_result.result if task_result.ready() else None
      ),  
  }

  return response

@router.post("/cancel/{task_id}")
async def cancel_report_task(task_id: str, current_user = Depends(get_current_user)):
    """
    Canceling a running or pending Celery task by its task_id.
    """
    task_result = AsyncResult(task_id, app=celery)

    if not task_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Task not found"
        )
    
    
    task_result.revoke(terminate=True, signal="SIGKILL")
    
    return {
        "status": "success",
        "message": f"Task {task_id} successfully cancelled",
        "task_id": task_id,
        "current_task_status": task_result.status
    }