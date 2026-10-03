#!/bin/bash
# Container start: migrate, seed (idempotent), serve.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding roles, the first admin and the starting dictionaries..."
python -m scripts.seed_data

# One process: it also runs the background task that closes warehouse days.
echo "Starting the application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*" --no-access-log
