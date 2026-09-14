#!/usr/bin/env bash

# Запускаем Celery в фоне с concurrency=1, чтобы вписываться в лимиты памяти Render
celery -A workers.celery_app:celery worker --concurrency=1 --loglevel=info &

# Запускаем Uvicorn в фокусном режиме, чтобы удерживать порт Render открытым
uvicorn main:app --host 0.0.0.0 --port $PORT