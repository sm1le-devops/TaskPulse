#!/usr/bin/env bash

# Запускаем Celery-воркер в фоновом режиме
celery -A workers.celery_app:celery worker --concurrency=1 --loglevel=info &

# Обязательно используем exec, чтобы Uvicorn стал главным процессом (PID 1) 
# и напрямую ответил Render на динамический порт $PORT
exec uvicorn main:app --host 0.0.0.0 --port $PORT