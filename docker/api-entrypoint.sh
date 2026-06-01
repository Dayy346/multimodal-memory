#!/bin/sh
set -e

echo "Waiting for Postgres..."
python <<'PY'
import os
import sys
import time

import psycopg

raw = os.environ.get("DATABASE_URL", "")
url = raw.replace("postgresql+psycopg://", "postgresql://", 1)
if not url:
    sys.exit("DATABASE_URL is not set")

for _ in range(90):
    try:
        with psycopg.connect(url, connect_timeout=3):
            break
    except Exception:
        time.sleep(1)
else:
    sys.exit("Timed out waiting for database")
PY

echo "Running migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
