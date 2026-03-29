from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    'pcb_defect_detection',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Периодические задачи
celery_app.conf.beat_schedule = {
    'cleanup-old-results': {
        'task': 'src.tasks.cleanup_tasks.cleanup_old_results',
        'schedule': crontab(hour=2, minute=0),  # Каждый день в 2:00
    },
    'generate-daily-report': {
        'task': 'src.tasks.report_tasks.generate_daily_report',
        'schedule': crontab(hour=0, minute=0),  # Каждый день в полночь
    },
}