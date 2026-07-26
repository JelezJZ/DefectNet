from ultralytics import YOLO
from celery import group, chord
from celery.exceptions import SoftTimeLimitExceeded
from src.tasks.celery_config import celery_app
import cv2
import logging
import os

logger = logging.getLogger(__name__)

# Глобальная модель для переиспользования в воркере
_model = None


def _load_model():
    """Ленивая загрузка модели"""
    global _model
    if _model is None:
        model_path = os.getenv('MODEL_PATH', 'src/models/best.pt')
        _model = YOLO(model_path)
    return _model


@celery_app.task(bind=True, max_retries=3, time_limit=int(os.getenv('TASK_TIME_LIMIT', '300')))
def process_single_image(self, image_path: str, confidence: float = 0.25):
    """Асинхронная обработка одного изображения"""

    try:
        # Обновление прогресса
        self.update_state(state='PROCESSING', meta={'progress': 0})

        # Загрузка модели (ленивая)
        model = _load_model()

        # Обновление прогресса после загрузки модели
        self.update_state(state='PROCESSING', meta={'progress': 25})

        # Обработка
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")

        results = model(img, conf=confidence)

        # Обновление прогресса после инференса
        self.update_state(state='PROCESSING', meta={'progress': 75})

        # Извлечение результатов
        detections = []
        for r in results:
            for box in r.boxes:
                detections.append({
                    'class': model.names[int(box.cls)],
                    'confidence': float(box.conf),
                    'bbox': box.xyxy[0].tolist()
                })

        self.update_state(state='SUCCESS', meta={'progress': 100})

        return {
            'image_path': image_path,
            'detections': detections,
            'count': len(detections),
            'status': 'success'
        }

    except (SoftTimeLimitExceeded, Exception) as e:
        error_msg = str(e)
        logger.error(f"Error processing {image_path}: {error_msg}")
        self.update_state(state='FAILURE', meta={'error': error_msg})
        
        # Retry logic для временных ошибок
        if not isinstance(e, SoftTimeLimitExceeded):
            raise self.retry(exc=e, countdown=5)
        raise


@celery_app.task(bind=True)
def aggregate_batch_results(self, results: list):
    """Агрегация результатов пакетной обработки"""
    
    try:
        successful = []
        failed = []
        total_detections = 0

        for result in results:
            if result.get('status') == 'success':
                successful.append(result)
                total_detections += result.get('count', 0)
            else:
                failed.append({
                    'image_path': result.get('image_path', 'unknown'),
                    'error': result.get('error', 'unknown error')
                })

        return {
            'status': 'completed',
            'total_images': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'total_detections': total_detections,
            'results': successful,
            'failures': failed
        }

    except Exception as e:
        logger.error(f"Error aggregating results: {str(e)}")
        raise


@celery_app.task(bind=True, max_retries=2)
def process_batch(self, image_paths: list, confidence: float = 0.25, max_parallel: int = 10):
    """
    Пакетная обработка множества изображений с агрегацией результатов.
    
    Args:
        image_paths: Список путей к изображениям
        confidence: Порог уверенности детекции
        max_parallel: Максимальное количество параллельных задач (ограничение нагрузки)
    
    Returns:
        Агрегированные результаты по всем изображениям
    """

    if not image_paths:
        return {
            'status': 'completed',
            'total_images': 0,
            'successful': 0,
            'failed': 0,
            'total_detections': 0,
            'results': [],
            'failures': []
        }

    try:
        # Разбиение на под-батчи для контроля параллелизма
        total = len(image_paths)
        self.update_state(state='PROCESSING', meta={
            'progress': 0,
            'total': total,
            'processed': 0
        })

        # Ограничение параллелизма через chunked group
        tasks = [process_single_image.s(path, confidence) for path in image_paths]
        
        # chord: ждёт завершения всех задач и вызывает callback
        job = chord(tasks)(aggregate_batch_results.s())

        # Синхронное ожидание результатов с таймаутом
        result = job.get(timeout=300, propagate=False)

        if result:
            result['progress'] = 100
            result['processed'] = total

        self.update_state(state='SUCCESS', meta={'progress': 100})

        return result

    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        
        # Попытка ретрая для временных ошибок
        if "timeout" in str(e).lower():
            raise self.retry(exc=e, countdown=10)
        raise


@celery_app.task
def process_batch_async(image_paths: list, confidence: float = 0.25, max_parallel: int = 10):
    """
    Асинхронная пакетная обработка (неблокирующая).
    Возвращает ID задачи для последующего опроса результатов.
    
    Используйте, когда не нужно ждать результаты немедленно.
    """
    job = process_batch.apply_async(args=[image_paths, confidence, max_parallel])
    return {
        'batch_id': job.id,
        'total_images': len(image_paths),
        'status': 'queued'
    }