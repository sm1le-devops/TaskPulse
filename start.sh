#!/usr/bin/env bash

# 1. Запускаем Celery-воркер в фоновом режиме
celery -A workers.celery_app:celery worker --loglevel=info &

# 2. Даем фоновому процессу секунду на инициализацию
sleep 1

# 3. Запускаем Uvicorn через exec, чтобы он перенял управление процессом и портом Render
exec uvicorn main:app --host 0.0.0.0 --port $PORT