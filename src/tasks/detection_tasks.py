import json
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from ultralytics import YOLO

from src.database.database import SessionLocal
from src.services.detection_cache import (
    build_cache_key,
    get_cached_result,
    set_cached_result,
)
from src.services.detection_pipeline import (
    build_defect_stats,
    build_detections,
    encode_visualization,
    get_inspection_status,
    save_result_visualization,
    save_uploaded_image,
)
from src.services.inspection_persistence import save_inspection_and_stats
from src.services.model_registry import discover_model_paths
from src.tasks.celery_config import celery_app

logger = get_task_logger(__name__)

_worker_model_cache: dict[str, tuple[YOLO, dict[str, str]]] = {}

DEFECT_INFO = {
    "mouse_bite": {
        "name_ru": "Мышиный укус",
        "severity": "medium",
        "description": "Неровные края на печатной плате",
    },
    "spur": {
        "name_ru": "Выступ",
        "severity": "low",
        "description": "Выступ на проводнике",
    },
    "short": {
        "name_ru": "Короткое замыкание",
        "severity": "critical",
        "description": "Нежелательное соединение проводников",
    },
    "open_circuit": {
        "name_ru": "Разрыв цепи",
        "severity": "critical",
        "description": "Разрыв проводника",
    },
    "spurious_copper": {
        "name_ru": "Лишняя медь",
        "severity": "medium",
        "description": "Остатки меди на плате",
    },
}

def _get_worker_model_and_version(model_name: str = "default") -> tuple[YOLO, dict[str, str]]:
    """
    A standalone caching model loader inside the Celery process.
    """

    from src.api.main import BASE_DIR

    global _worker_model_cache

    selected_name = model_name or "default"

    if selected_name in _worker_model_cache:
        return _worker_model_cache[selected_name]

    default_model_path = os.getenv(
        "MODEL_PATH", "models/trained/pcb_defect_detector_v13_best.pt"
    )
    target_path = default_model_path

    config_path = BASE_DIR / "src" / "models" / "models_config.json"

    available_model_paths = discover_model_paths(
        default_model_path=default_model_path,
        models_config_path=config_path,
    )

    model_versions = {name: "unknown" for name in available_model_paths.keys()}
    
    if selected_name != "default" and config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                models_dict = config.get("models", {})
                if selected_name in models_dict:
                    target_path = models_dict[selected_name].get("path", target_path)
                for name, info in config.get("models", {}).items():
                    if name in model_versions:
                        model_versions[name] = str(info.get("version", "unknown"))
        except Exception as e:
            logger.warning("Failed to read models_config.json in Celery: %s", str(e))

    model_file = Path(target_path)
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found at path: {target_path}")

    logger.info("Loading YOLO model '%s' from %s...", selected_name, target_path)
    loaded_model = YOLO(str(model_file))
    
    _worker_model_cache[selected_name] = (loaded_model, model_versions)
    return loaded_model, model_versions


@celery_app.task(
    bind=True, 
    max_retries=2, 
    time_limit=int(os.getenv("TASK_TIME_LIMIT", "300"))
)
def process_single_image(
    self,
    filename: str = None,
    image_path: str = None, 
    confidence: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 1024,
    model_name: str = "default",
    save_image: bool = True,
) -> dict:
    """Asynchronous processing of a single image"""

    from src.api.main import (
        RESULTS_DIR,
        UPLOAD_DIR,
    )

    start_time = time.time()

    inspection_id = str(uuid.uuid4())

    req_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    req_unique_id = uuid.uuid4().hex[:8]
    req_base_filename = f"{req_timestamp}_{req_unique_id}"

    try:
        self.update_state(state="PROCESSING", meta={"progress": 10})

        path_obj = Path(image_path)
        if not path_obj.exists() or path_obj.stat().st_size == 0:
            return {"image_path": image_path, "status": "error", "error": "File missing or zero size"}

        with open(image_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)

        contents = file_bytes.tobytes()
        
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if img is None:
            return {
                "image_path": image_path,
                "status": "error",
                "error": "Corrupted or invalid image file",
            }

        self.update_state(state="PROCESSING", meta={"progress": 30})

        height, width = img.shape[:2]

        model, model_versions = _get_worker_model_and_version(model_name)
        model_version = model_versions.get(model_name, "unknown")

        cache_key = build_cache_key(
            image_bytes=contents,
            model_name=model_name,
            confidence=confidence,
            iou=iou,
            imgsz=imgsz,
        )

        cached_result =  get_cached_result(cache_key)

        now = datetime.now()
        date_dir = now.strftime("%Y/%m/%d")
        session_dir_name = inspection_id
        upload_session_dir = UPLOAD_DIR / date_dir / session_dir_name
        result_session_dir = RESULTS_DIR / date_dir / session_dir_name
        upload_session_dir.mkdir(parents=True, exist_ok=True)
        result_session_dir.mkdir(parents=True, exist_ok=True)

        upload_image_path = save_uploaded_image(
            contents, filename, upload_session_dir, req_base_filename
        )

        augment = os.getenv("AUGMENT", "True").lower() == "true"

        if cached_result:
            detections = cached_result["detections"]
            severity_counts = cached_result["severity_counts"]
            total_defects = cached_result["total_defects"]
            inspection_status = cached_result["inspection_status"]
            annotated_image = cached_result.get("annotated_image")
        else:
            results = model(img, conf=confidence, iou=iou, imgsz=imgsz, augment=augment)

            detections, severity_counts = build_detections(
                results, model.names, DEFECT_INFO
            )

            total_defects = len(detections)

            inspection_status = get_inspection_status(severity_counts)

            annotated_image = encode_visualization(results) if detections else None

            set_cached_result(
                cache_key,
                {
                    "detections": detections,
                    "severity_counts": severity_counts,
                    "total_defects": total_defects,
                    "inspection_status": inspection_status,
                    "annotated_image": annotated_image,
                },
            )

        result_image_path, _ = save_result_visualization(
            annotated_image, save_image, result_session_dir, req_base_filename
        )
        if result_image_path:
            result_image_url = (
                "/results/" + result_image_path.relative_to(RESULTS_DIR).as_posix()
            )
        else:
            result_image_url = None

        stats_map = build_defect_stats(detections)

        processing_time = round(time.time() - start_time, 4)

        return {
            "status": "success",
            "inspection_id": inspection_id,
            "image_path": image_path,
            "filename": filename or path_obj.name,
            "image_width": width,
            "image_height": height,
            "confidence": confidence,
            "model_name": model_name,
            "model_version": model_version,
            "detections": detections,
            "total_defects": total_defects,
            "inspection_status": inspection_status,
            "severity_counts": severity_counts,
            "upload_image_path": str(upload_image_path) if upload_image_path else None,
            "result_image_path": str(result_image_path) if result_image_path else None,
            "result_image_url": result_image_url,
            "processing_time": processing_time,
            "stats_map": stats_map,
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
def aggregate_batch_results(
    self, 
    results: list, 
    user_id: int = None,
    batch_dir: str = None,
) -> dict[str, Any]:
    """Aggregation of batch processing results"""

    try:
        successful = []
        failed = []
        total_detections = 0

        for result in results:
            if isinstance(result, dict) and result.get("status") == "success":
                successful.append(result)
                total_detections += result.get("total_defects", 0)
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

        if successful:
            with SessionLocal() as db:
                try:
                    for item in successful:
                        save_inspection_and_stats(
                            db=db,
                            inspection_id=item["inspection_id"],
                            filename=item["filename"],
                            image_width=item["image_width"],
                            image_height=item["image_height"],
                            confidence_threshold=item["confidence"],
                            model_name=item["model_name"],
                            model_version=item["model_version"],
                            total_defects=item["total_defects"],
                            inspection_status=item["inspection_status"],
                            severity_counts=item["severity_counts"],
                            detections=item["detections"],
                            upload_path=item.get("upload_image_path"),
                            result_image_path=item.get("result_image_path"),
                            processing_time=item["processing_time"],
                            operator_id=str(user_id),
                            stats_map=item["stats_map"],
                        )
                    logger.info("Successfully saved %d inspections to DB via save_inspection_and_stats", len(successful))
                except Exception as e:
                    logger.error("Failed batch DB save: %s", str(e))

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
    finally:
        if batch_dir and Path(batch_dir).exists():
            shutil.rmtree(batch_dir, ignore_errors=True)