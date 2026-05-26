# Configuration Guide

This guide explains all available environment variables for DefectNet.

## Quick Start

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and adjust values for your environment

3. **IMPORTANT**: Generate a secure JWT secret key:
   ```bash
   openssl rand -hex 32
   ```
   Replace `your-secret-key-change-this-in-production` with the output

## Configuration Sections

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `True` | Enable debug mode |
| `ENVIRONMENT` | `development` | Environment name (`development`/`production`) |
| `WORKERS` | `1` | Number of worker processes |

### Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///pcb_defects.db` | Database connection string |
| `DB_POOL_SIZE` | `5` | Database connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections |

**Database URL Examples:**
- SQLite: `sqlite:///pcb_defects.db`
- PostgreSQL: `postgresql://user:password@localhost:5432/defectnet`
- MySQL: `mysql://user:password@localhost:3306/defectnet`

### JWT / Auth Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | *(change this!)* | Secret key for JWT token signing |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiration time (24 hours) |

### Model Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/trained/best.pt` | Path to YOLO model file |
| `DEFAULT_CONFIDENCE` | `0.25` | Default detection confidence threshold |
| `IMAGE_SIZE` | `1024` | Input image size for model |
| `IOU_THRESHOLD` | `0.45` | IoU threshold for NMS |
| `AUGMENT` | `True` | Enable test-time augmentation |

### Storage Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_DIR` | `storage` | Base storage directory |
| `UPLOAD_DIR` | `storage/uploads` | Uploaded images directory |
| `RESULTS_DIR` | `storage/results` | Result images directory |
| `REPORTS_DIR` | `storage/reports` | PDF reports directory |
| `EXPORTS_DIR` | `storage/exports` | CSV exports directory |

### File Upload Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum file upload size in MB |
| `ALLOWED_IMAGE_TYPES` | `image/jpeg,image/png,image/webp` | Allowed MIME types (comma-separated) |

### CORS Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |

If `ENVIRONMENT=production`, wildcard `*` in `ALLOWED_ORIGINS` is rejected at startup.

### API Security

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_PER_MINUTE` | `100` | Per-IP request limit per minute |

**Example for production:**
```
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Redis / Celery Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis broker URL for Celery |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Redis result backend URL |
| `CELERY_TIMEZONE` | `UTC` | Celery timezone |

### Batch Processing Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_BATCH_SIZE` | `20` | Maximum images per batch |
| `MAX_PARALLEL_TASKS` | `10` | Maximum parallel task execution |
| `TASK_TIME_LIMIT` | `300` | Task timeout in seconds (5 minutes) |

### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FORMAT` | `text` | Log format (text, json) |
| `LOG_DIR` | `logs` | Directory for rotating log files |
| `LOG_FILE` | `app.log` | Log filename |
| `LOG_MAX_BYTES` | `10485760` | Max size of one log file before rotation |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated files to keep |

### Cleanup Scheduler

| Variable | Default | Description |
|----------|---------|-------------|
| `CLEANUP_MAX_AGE_HOURS` | `24` | TTL for temp/batch artifacts |
| `CLEANUP_SCHEDULE_HOUR` | `2` | Daily cleanup hour (Celery beat) |
| `CLEANUP_SCHEDULE_MINUTE` | `0` | Daily cleanup minute (Celery beat) |

## Production Checklist

- [ ] Generate secure `JWT_SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure proper `DATABASE_URL` (PostgreSQL recommended)
- [ ] Set specific `ALLOWED_ORIGINS` (not `*`)
- [ ] Adjust `MAX_UPLOAD_SIZE_MB` based on your needs
- [ ] Configure Redis if using Celery workers
- [ ] Set appropriate `LOG_LEVEL` (WARNING or ERROR for production)
