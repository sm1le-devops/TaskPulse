#!/bin/sh

celery -A workers.celery_app:celery worker --loglevel=info &
CELERY_PID=$!

uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} &
UVICORN_PID=$!

trap 'kill $CELERY_PID $UVICORN_PID' SIGTERM SIGINT

wait -n $CELERY_PID $UVICORN_PID