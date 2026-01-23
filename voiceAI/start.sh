#!/bin/bash
set -e

# echo "Starting RabbitMQ email worker..."
# python -m app.workers.task_email &

# echo "Starting RabbitMQ audio worker..."
# python -m app.workers.task_audio &

echo "Starting Celery worker..."
celery -A app.common.celery worker -l info &

echo "Starting Django server..."
exec uvicorn voiceAI.asgi:application \
  --host 0.0.0.0 \
  --port 8000 \
  --timeout-graceful-shutdown 30 \
  --lifespan on

