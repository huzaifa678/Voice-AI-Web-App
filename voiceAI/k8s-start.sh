#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

ENV_FILE="$SCRIPT_DIR/../.env.docker"

echo "Using env file: $ENV_FILE"

if [ -f "$ENV_FILE" ] && [ -z "$KUBERNETES_SERVICE_HOST" ]; then
    echo "kubernetes host: $KUBERNETES_SERVICE_HOST"
    echo "Using env file: $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
fi

env | grep -E 'RABBITMQ|REDIS|GRPC'

echo "Using env file: $ENV_FILE"

: "${RABBITMQ_HOST:=$(echo $RABBITMQ_URL | sed -E 's|amqp://[^@]+@([^:]+):.*|\1|')}"
echo "RabbitMQ host resolved to: $RABBITMQ_HOST"

if [ -n "$KUBERNETES_SERVICE_HOST" ]; then

    echo "Waiting for RabbitMQ at $RABBITMQ_HOST:5672 ..."
    ./wait-for-it.sh "$RABBITMQ_HOST:5672" --timeout=60 -- echo "RabbitMQ is ready"
fi

echo "Starting RabbitMQ email worker..."
python -m app.workers.task_email &

echo "Starting Django server..."
exec uvicorn voiceAI.asgi:application \
  --host 0.0.0.0 \
  --port 8000 \
  --timeout-graceful-shutdown 30 \
  --lifespan on