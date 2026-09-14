#!/usr/bin/env bash

# Запускаем Celery-воркер в фоновом режиме и перенаправляем логи, чтобы они не терялись
celery -A workers.celery_app:celery worker --loglevel=info &

# Даем воркеру секунду на инициализацию
sleep 1

# Запускаем Uvicorn через exec, чтобы он стал главным процессом контейнера и занял порт Render ($PORT)
exec uvicorn main:app --host 0.0.0.0 --port $PORT