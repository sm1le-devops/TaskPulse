#!/bin/sh

# Запускаем Celery worker в фоне
celery -A workers.celery_app:celery worker --loglevel=info &

# Запускаем FastAPI через Uvicorn на динамическом порту Render
uvicorn main:app --host 0.0.0.0 --port $PORT