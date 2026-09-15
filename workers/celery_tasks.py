import time

from core.logger import logger
from db.database import SessionLocal
from models.models import Task, User
from workers.celery_app import celery


@celery.task(name="send_welcome_email_task")
def send_welcome_email_task(email: str):
    logger.info(f"Celery Worker: Starting email dispatch for {email}...")
    time.sleep(5)
    logger.info(f"Celery Worker: Email successfully sent to {email}!")
    return {"status": "success", "email": email}


@celery.task(bind=True, name="generate_user_report_task")
def generate_user_report_task(self, user_email: str):
    """Real task: collects statistics on user tasks from the database."""
    task_id = self.request.id
    logger.info(
        f"Celery Worker: Start generating report for {user_email} (Task ID: {task_id})"
    )

    # Open a database session directly inside the worker
    db = SessionLocal()
    try:
        # Look up user by email
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return {"error": "User not found"}

        # Simulate a long calculation (e.g., heavy computations or export)
        time.sleep(4)

        # Count their tasks from the tasks table
        total_tasks = db.query(Task).filter(Task.user_id == user.id).count()
        completed_tasks = (
            db.query(Task)
            .filter(Task.user_id == user.id, Task.completed == True)
            .count()
        )

        report_data = {
            "user_email": user_email,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": total_tasks - completed_tasks,
            "status": "completed",
        }

        logger.info(f"Celery Worker: Report for {user_email} successfully generated!")
        return report_data

    except Exception as e:
        logger.error(f"Error generating report: {e!s}")
        raise
    finally:
        db.close()  # Make sure to close the session!
