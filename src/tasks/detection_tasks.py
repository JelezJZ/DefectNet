import json
import logging
import os
from pathlib import Path

import cv2
from celery.exceptions import SoftTimeLimitExceeded
from ultralytics import YOLO

from src.tasks.celery_config import celery_app

logger = logging.getLogger(__name__)

_worker_model_cache = {}


def _get_worker_model(model_name: str = "default") -> YOLO:
    """
    A standalone caching model loader inside the Celery process.
    """
    global _worker_model_cache

    selected_name = model_name or "default"

    if selected_name in _worker_model_cache:
        return _worker_model_cache[selected_name]

    default_model_path = os.getenv(
        "MODEL_PATH", "models/trained/pcb_defect_detector_v13_best.pt"
    )
    target_path = default_model_path

    config_path = Path("src/models/models_config.json")
    if selected_name != "default" and config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                models_dict = config.get("models", {})
                if selected_name in models_dict:
                    target_path = models_dict[selected_name].get("path", target_path)
        except Exception as e:
            logger.warning("Failed to read models_config.json in Celery: %s", str(e))

    model_file = Path(target_path)
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found at path: {target_path}")

    logger.info("Loading YOLO model '%s' from %s...", selected_name, target_path)
    loaded_model = YOLO(str(model_file))
    
    _worker_model_cache[selected_name] = loaded_model
    return loaded_model


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

        model = _get_worker_model(model_name)
        
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
