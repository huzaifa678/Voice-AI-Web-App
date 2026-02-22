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

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-voiceAI.settings}
echo "DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"

if [ -n "$POSTGRES_HOST" ]; then
    echo "Waiting for PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT ..."
    ./wait-for-it.sh "$POSTGRES_HOST:$POSTGRES_PORT" --timeout=60 -- echo "PostgreSQL is ready"
fi

echo "Starting gRPC server..."
exec python -m app.grpc.start