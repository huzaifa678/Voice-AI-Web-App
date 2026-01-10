#!/bin/bash

echo "Starting RabbitMQ email worker..."
python -m app.workers.task_email &

echo "Starting RabbitMQ audio worker..."
python -m app.workers.task_audio &

echo "Starting Django server..."
python manage.py runserver

