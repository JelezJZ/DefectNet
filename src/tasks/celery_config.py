from celery import Celery
from celery.schedules import crontab
import os
from src.core.logging_config import setup_logging

setup_logging()

celery_app = Celery(
    'pcb_defect_detection',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['src.tasks.detection_tasks', 'src.tasks.cleanup_tasks'],
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=os.getenv('CELERY_TIMEZONE', 'UTC'),
    enable_utc=True,
)

# Periodic cleanup of old temporary artifacts.
cleanup_hour = int(os.getenv('CLEANUP_SCHEDULE_HOUR', '2'))
cleanup_minute = int(os.getenv('CLEANUP_SCHEDULE_MINUTE', '0'))

celery_app.conf.beat_schedule = {
    'cleanup-old-temp-files': {
        'task': 'src.tasks.cleanup_tasks.cleanup_old_temp_files',
        'schedule': crontab(hour=cleanup_hour, minute=cleanup_minute),
    }
}
