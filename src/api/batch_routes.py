import uuid
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File
from celery.result import AsyncResult

router = APIRouter(prefix="/batch", tags=["Batch Processing"])

@router.post("/upload")
async def upload_batch(files: List[UploadFile] = File(...)):
    """Загрузка пакета изображений для обработки"""
    
    image_paths = []
    batch_dir = Path(f"batch_{uuid.uuid4()}")
    batch_dir.mkdir(exist_ok=True)
    
    for file in files:
        file_path = batch_dir / file.filename
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        image_paths.append(str(file_path))
    
    # Запуск асинхронной обработки
    from src.tasks.detection_tasks import process_batch
    result = process_batch.delay(image_paths)
    
    return {
        'batch_id': result.id,
        'total_images': len(files),
        'status': 'queued',
        'status_url': f'/batch/status/{result.id}'
    }

@router.get("/status/{batch_id}")
async def get_batch_status(batch_id: str):
    """Проверка статуса пакетной обработки"""
    
    result = AsyncResult(batch_id)
    
    if result.state == 'PENDING':
        response = {
            'state': result.state,
            'status': 'Pending...'
        }
    elif result.state == 'PROCESSING':
        response = {
            'state': result.state,
            'progress': result.info.get('progress', 0),
            'status': 'Processing...'
        }
    elif result.state == 'SUCCESS':
        response = {
            'state': result.state,
            'result': result.result,
            'status': 'Completed'
        }
    else:
        response = {
            'state': result.state,
            'status': str(result.info)
        }
    
    return response
