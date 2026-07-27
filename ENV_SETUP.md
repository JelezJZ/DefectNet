# Environment Setup (Current)

This document reflects the current state of the project setup and complements `CONFIG.md`.

## Quick Start

```bash
cp .env.example .env
python -m src.api.main
```

## Critical Variables

- `DB_DRIVER`, `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME` — required for database connection; the backend will fail to start without them.
- `MODEL_PATH` — must point to an existing `.pt` file, otherwise startup will crash with an error.
- `JWT_SECRET_KEY` — replace the default value before any public deployment.

## Configurable via `.env`

- Server / Environment: `HOST`, `PORT`, `DEBUG`, `ENVIRONMENT`
- Database: `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`
- Detection: `MODEL_PATH`, `IMAGE_SIZE`, `IOU_THRESHOLD`, `AUGMENT`
- File Uploads: `MAX_UPLOAD_SIZE_MB`, `ALLOWED_IMAGE_TYPES`
- CORS: `ALLOWED_ORIGINS`
- Rate Limiting: `RATE_LIMIT_PER_MINUTE`
- Celery / Redis: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TIMEZONE`
- Batch Processing: `MAX_BATCH_SIZE`, `TASK_TIME_LIMIT`
- Logging: `LOG_LEVEL`, `LOG_FORMAT`, `LOG_DIR`, `LOG_FILE`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`
- Temporary File Cleanup: `CLEANUP_MAX_AGE_HOURS`, `CLEANUP_SCHEDULE_HOUR`, `CLEANUP_SCHEDULE_MINUTE`

## Important Restrictions

- In `ENVIRONMENT=production` mode, `ALLOWED_ORIGINS=*` is strictly disallowed.
- The frontend is served directly by the backend (`/` and `/dashboard`); a standalone `frontend/env-config.js` is currently not evaluated at runtime.