import os

from celery import Celery

broker_url = os.getenv("REDIS_URL_BROKER", "redis://redis_broker:6379/0")

result_backend = os.getenv("REDIS_URL_CACHE", "redis://redis_broker:6379/1")

celery = Celery(
    "fastapi_app",
    broker=broker_url,
    backend=result_backend,
    include=["workers.celery_tasks"],
)

celery.conf.update(
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "False") == "True",
    task_eager_propagates=True,
    # ВАЖНО для pytest + eager mode
    task_store_eager_result=True,
)
