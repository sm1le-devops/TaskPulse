import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL_BROKER", "redis://localhost:6379/0")

celery = Celery(
    "fastapi_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.celery_tasks"]
)