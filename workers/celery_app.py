# workers/celery_app.py
import os
from celery import Celery

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery = Celery(
    "fastapi_app",
    broker=broker_url,
    backend=result_backend
)

celery.conf.update(
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "False") == "True",
    task_eager_propagates=True,
)