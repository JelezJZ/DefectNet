import uuid
import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, Depends
from celery.result import AsyncResult
from src.database.models import User
from src.auth.jwt_handler import get_current_user
from src.services.detection_pipeline import validate_image_upload

router = APIRouter(prefix="/batch", tags=["Batch Processing"])

@router.post("/upload")
async def upload_batch(files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user)):
    """Загрузка пакета изображений для обработки"""
    
    image_paths = []
    batch_dir = Path(f"batch_{uuid.uuid4()}")
    batch_dir.mkdir(exist_ok=True)

    max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    allowed_image_types = {
        image_type.strip()
        for image_type in os.getenv(
            "ALLOWED_IMAGE_TYPES", "image/jpeg,image/png,image/webp"
        ).split(",")
        if image_type.strip()
    }
    
    for file in files:
        file_path = batch_dir / file.filename
        contents = await file.read()
        validate_image_upload(file, contents, max_upload_size_mb, allowed_image_types)
        with open(file_path, 'wb') as f:
            f.write(contents)
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
async def get_batch_status(batch_id: str, current_user: User = Depends(get_current_user)):
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
