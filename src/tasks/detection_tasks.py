import logging
import os
from pathlib import Path

import cv2
from celery.exceptions import SoftTimeLimitExceeded
from ultralytics import YOLO

from src.tasks.celery_config import celery_app

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    """Lazy loading of the model"""
    global _model
    if _model is None:
        model_path = os.getenv(
            "MODEL_PATH", "models/trained/pcb_defect_detector_v13_best.pt"
        )
        _model = YOLO(model_path)
    return _model


@celery_app.task(
    bind=True, max_retries=2, time_limit=int(os.getenv("TASK_TIME_LIMIT", "300"))
)
def process_single_image(
    self, 
    image_path: str, 
    confidence: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 1024,
    model_name: str = "default",
):
    """Asynchronous processing of a single image"""

    try:
        self.update_state(state="PROCESSING", meta={"progress": 10})

        if not Path(image_path).exists():
            return {
                "image_path": image_path,
                "status": "error",
                "error": "File not found on disk",
            }

        img = cv2.imread(image_path)
        if img is None:
            return {
                "image_path": image_path,
                "status": "error",
                "error": "Corrupted or invalid image file",
            }

        self.update_state(state="PROCESSING", meta={"progress": 30})

        model = _load_model()
        
        results = model(img, conf=confidence, iou=iou, imgsz=imgsz)
        
        self.update_state(state="PROCESSING", meta={"progress": 80})

        detections = []
        for r in results:
            for box in r.boxes:
                detections.append(
                    {
                        "class": model.names[int(box.cls)],
                        "confidence": float(box.conf),
                        "bbox": box.xyxy[0].tolist(),
                    }
                )

        return {
            "image_path": image_path,
            "detections": detections,
            "count": len(detections),
            "status": "success",
        }

    except SoftTimeLimitExceeded:
        logger.error(f"Time limit exceeded for image: {image_path}")
        return {
            "image_path": image_path,
            "status": "error",
            "error": "Task processing timed out",
        }

    except Exception as e:
        logger.error(f"Unexpected error processing {image_path}: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=5)
        except self.MaxRetriesExceededError:
            return {
                "image_path": image_path,
                "status": "error",
                "error": f"Failed after max retries: {str(e)}",
            }


@celery_app.task(bind=True)
def aggregate_batch_results(self, results: list):
    """Aggregation of batch processing results"""

    try:
        successful = []
        failed = []
        total_detections = 0

        for result in results:
            if isinstance(result, dict) and result.get("status") == "success":
                successful.append(result)
                total_detections += result.get("count", 0)
            else:
                error_msg = (
                    result.get("error", "Unknown error")
                    if isinstance(result, dict)
                    else str(result)
                )
                image_path = (
                    result.get("image_path", "unknown")
                    if isinstance(result, dict)
                    else "unknown"
                )
                failed.append({"image_path": image_path, "error": error_msg})

        return {
            "status": "completed",
            "total_images": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_detections": total_detections,
            "results": successful,
            "failures": failed,
        }

    except Exception as e:
        logger.error(f"Error aggregating results: {str(e)}")
        raise
