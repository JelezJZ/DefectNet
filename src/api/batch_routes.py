import os
import shutil
import uuid
from pathlib import Path

from celery import chord
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from src.api.detect_routes import _validate_detection_params
from src.auth.jwt_handler import get_current_user
from src.database.models import User
from src.services.detection_pipeline import validate_image_upload
from src.tasks.celery_config import celery_app
from src.tasks.detection_tasks import aggregate_batch_results, process_single_image

router = APIRouter(prefix="/batch", tags=["Batch Processing"])


def _save_bytes_sync(file_path: Path, contents: bytes) -> None:
    """Writing bytes to disk in a separate stream"""
    with open(file_path, "wb") as f:
        f.write(contents)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(
    files: list[UploadFile] = File(...),
    confidence: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 1024,
    model_name: str = "default",
    current_user: User = Depends(get_current_user),
):
    """Loading a batch of images for processing"""

    max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "20"))
    if len(files) > max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {max_batch_size} images allowed per batch",
        )

    _validate_detection_params(confidence, iou, imgsz)

    max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    allowed_types = {
        t.strip()
        for t in os.getenv(
            "ALLOWED_IMAGE_TYPES", "image/jpeg,image/png,image/webp"
        ).split(",")
        if t.strip()
    }

    base_storage = Path(os.getenv("STORAGE_DIR", "storage"))
    batch_id = str(uuid.uuid4())
    batch_dir = base_storage / "temp" / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    image_paths = []

    try:
        for file in files:
            await file.seek(0)
            contents = await file.read()

            if not contents or len(contents) == 0:
                raise HTTPException(
                    status_code=400, detail=f"File {file.filename} is empty"
                )

            validate_image_upload(file, contents, max_upload_size_mb, allowed_types)

            file_ext = Path(file.filename).suffix.lower() or ".jpg"
            safe_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = batch_dir / safe_filename

            await run_in_threadpool(_save_bytes_sync, file_path, contents)

            image_paths.append(str(file_path))

    except Exception as err:
        if batch_dir.exists():
            shutil.rmtree(batch_dir, ignore_errors=True)
        if isinstance(err, HTTPException):
            raise err
        raise HTTPException(
            status_code=500, detail=f"Failed to process upload: {str(err)}"
        )

    tasks = [
        process_single_image.s(
            image_path=path,
            confidence=confidence,
            iou=iou,
            imgsz=imgsz,
            model_name=model_name,
        )
        for path in image_paths
    ]

    job = chord(tasks)(aggregate_batch_results.s())

    return {
        "batch_id": job.id,
        "total_images": len(image_paths),
        "status": "queued",
        "status_url": f"/api/v1/batch/status/{job.id}",
    }


@router.get("/status/{batch_id}")
async def get_batch_status(
    batch_id: str, current_user: User = Depends(get_current_user)
):
    """Checking batch processing status"""

    result = AsyncResult(batch_id, app=celery_app)

    state = result.state
    info = result.info

    if state == "PENDING":
        return {
            "batch_id": batch_id, 
            "state": state, 
            "status": "Processing images in batch..."
        }
    
    elif state == "PROCESSING":
        progress = 0
        if isinstance(info, dict):
            progress = info.get("progress", 0)

        return {
            "batch_id": batch_id, 
            "state": state,
            "progress": progress,
            "status": "Aggregating results...",
        }

    elif state == "SUCCESS":
        return {
            "batch_id": batch_id, 
            "state": state,
            "status": "Completed",
            "result": result.result,
        }

    elif state == "FAILURE":
        error_message = str(info) if info else "Unknown error occurred"
        return {
            "batch_id": batch_id, 
            "state": state,
            "status": "Failed",
            "error": error_message,
        }
    
    return {
        "batch_id": batch_id, 
        "state": state, 
        "status": str(info) if info else state,
    }
