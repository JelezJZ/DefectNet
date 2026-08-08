#!/bin/sh
set -e

echo "Waiting for database at ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}..."

python - <<'PY'
import os
import sys
import time
from sqlalchemy import create_engine, text
from src.database.database import db_url

url = db_url.render_as_string(hide_password=False)
engine = create_engine(url, pool_pre_ping=True)
for attempt in range(int(os.getenv("DB_WAIT_RETRIES", "60"))):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except Exception as exc:
        if attempt % 5 == 0:
            print(f"  DB not ready ({exc.__class__.__name__}); retrying...")
        time.sleep(2)
else:
    print("Database did not become ready in time.", file=sys.stderr)
    sys.exit(1)
engine.dispose()
print("Database is ready.")
PY

echo "Applying Alembic migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn src.api.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-1}"