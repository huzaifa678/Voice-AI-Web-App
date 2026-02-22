#!/bin/sh
set -e

BACKEND_URL="http://voice-ai:8000/health/"
TIMEOUT=120
INTERVAL=2
ELAPSED=0

echo "Waiting for backend at $BACKEND_URL"

until curl -sf "$BACKEND_URL"; do
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo "Backend never became ready"
    exit 1
  fi
done

echo "Backend is ready, running tests"
DJANGO_TEST=true pytest -v