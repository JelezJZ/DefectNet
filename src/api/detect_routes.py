import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.auth.jwt_handler import get_current_user
from src.database.database import get_db
from src.database.models import User
from src.services.detection_cache import (
    build_cache_key,
    get_cached_result,
    set_cached_result,
)
from src.services.detection_pipeline import (
    build_defect_stats,
    build_detections,
    decode_image,
    get_inspection_status,
    run_inference,
    save_result_visualization,
    save_uploaded_image,
    validate_image_upload,
)
from src.services.detection_response import build_detection_response
from src.services.inspection_persistence import save_inspection_and_stats
from src.services.model_registry import get_or_load_model

router = APIRouter(prefix="/detect", tags=["Detect"])


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
    "missing_hole": {
        "name_ru": "Отсутствующее отверстие",
        "severity": "critical",
        "description": "Отверстие не просверлено или отсутствует",
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


@router.post("/")
async def detect_defects(
    file: UploadFile = File(...),
    confidence: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 1024,
    model_name: str = "default",
    save_image: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Основной endpoint для детекции дефектов

    Args:
        file: Изображение печатной платы
        confidence: Порог уверенности (0.0-1.0)
        save_image: Сохранять ли изображение с результатами
        db: Зависимость БД
        current_user: Текущий пользователь
    """
    _validate_detection_params(confidence, iou, imgsz)
    return await _process_detection(
        file, confidence, iou, imgsz, model_name, save_image, db, current_user
    )


@router.post("/batch-detect")
async def batch_detect(
    files: list[UploadFile] = File(...),
    confidence: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 1024,
    model_name: str = "default",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пакетная обработка нескольких изображений"""

    max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "20"))
    if len(files) > max_batch_size:
        raise HTTPException(
            status_code=400, detail=f"Maximum {max_batch_size} images per batch"
        )

    _validate_detection_params(confidence, iou, imgsz)

    results_list = []

    for file in files:
        try:
            # Вызываем внутреннюю функцию detect для каждого файла
            result = await _process_detection(
                file,
                confidence,
                iou,
                imgsz,
                model_name,
                save_image=True,
                db=db,
                current_user=current_user,
            )
            results_list.append(
                {"filename": file.filename, "status": "success", "data": result}
            )
        except Exception as e:
            results_list.append(
                {"filename": file.filename, "status": "error", "error": str(e)}
            )

    return {
        "batch_id": str(uuid.uuid4()),
        "total_images": len(files),
        "processed": len(results_list),
        "results": results_list,
    }


@router.get("/defect-info")
async def get_defect_info(current_user: User = Depends(get_current_user)):
    """Получите информацию о типах дефектов"""
    return DEFECT_INFO


async def _process_detection(
    file: UploadFile,
    confidence: float,
    iou_threshold: float,
    image_size: int,
    model_name: str,
    save_image: bool,
    db: Session,
    current_user: User,
):
    """
    Внутренняя функция для детекции дефектов (без FastAPI зависимостей)
    """

    from src.api.main import (
        RESULTS_DIR,
        UPLOAD_DIR,
        available_model_paths,
        model,
        model_cache,
        model_versions,
    )

    start_time = time.time()
    inspection_id = str(uuid.uuid4())

    req_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    req_unique_id = uuid.uuid4().hex[:8]
    req_base_filename = f"{req_timestamp}_{req_unique_id}"

    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        selected_model, selected_model_name = get_or_load_model(
            model_name=model_name,
            model_cache=model_cache,
            model_paths=available_model_paths,
        )

        contents = await file.read()
        max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
        allowed_image_types = {
            image_type.strip()
            for image_type in os.getenv(
                "ALLOWED_IMAGE_TYPES", "image/jpeg,image/png,image/webp"
            ).split(",")
            if image_type.strip()
        }
        validate_image_upload(file, contents, max_upload_size_mb, allowed_image_types)

        cache_key = build_cache_key(
            image_bytes=contents,
            model_name=selected_model_name,
            confidence=confidence,
            iou=iou_threshold,
            imgsz=image_size,
        )
        cached_result = get_cached_result(cache_key)

        now = datetime.now()
        date_dir = now.strftime("%Y/%m/%d")
        session_dir_name = inspection_id
        upload_session_dir = UPLOAD_DIR / date_dir / session_dir_name
        result_session_dir = RESULTS_DIR / date_dir / session_dir_name
        upload_session_dir.mkdir(parents=True, exist_ok=True)
        result_session_dir.mkdir(parents=True, exist_ok=True)

        upload_path = save_uploaded_image(
            contents, file.filename, upload_session_dir, req_base_filename
        )
        img = decode_image(contents)

        augment = os.getenv("AUGMENT", "True").lower() == "true"

        if cached_result:
            detections = cached_result["detections"]
            severity_counts = cached_result["severity_counts"]
            total_defects = cached_result["total_defects"]
            inspection_status = cached_result["inspection_status"]

            cached_result_image_path = cached_result.get("result_image_path")
            result_image_path = None
            result_image_url = None

            if (
                save_image
                and cached_result_image_path
                and Path(cached_result_image_path).exists()
            ):
                result_image_path = Path(cached_result_image_path)
                path_parts = result_image_path.relative_to(RESULTS_DIR).parts
                result_image_url = "/results/" + "/".join(path_parts)
        else:
            results = run_inference(
                selected_model, img, confidence, image_size, iou_threshold, augment
            )
            detections, severity_counts = build_detections(
                results, selected_model.names, DEFECT_INFO
            )
            total_defects = len(detections)
            result_image_path, result_image_url = save_result_visualization(
                results, detections, save_image, result_session_dir, req_base_filename
            )
            if result_image_url:
                result_image_url = f"/results/{date_dir}/{session_dir_name}/result_{req_base_filename}.jpg"
            inspection_status = get_inspection_status(severity_counts)

            set_cached_result(
                cache_key,
                {
                    "detections": detections,
                    "severity_counts": severity_counts,
                    "total_defects": total_defects,
                    "inspection_status": inspection_status,
                    "result_image_path": str(result_image_path)
                    if result_image_path
                    else None,
                },
            )

        selected_model_version = model_versions.get(selected_model_name, "unknown")

        response = build_detection_response(
            inspection_id=inspection_id,
            filename=file.filename,
            image_width=img.shape[1],
            image_height=img.shape[0],
            confidence_threshold=confidence,
            model_name=selected_model_name,
            model_version=selected_model_version,
            total_defects=total_defects,
            inspection_status=inspection_status,
            severity_counts=severity_counts,
            detections=detections,
            result_image_url=result_image_url,
        )

        stats_map = build_defect_stats(detections)
        save_inspection_and_stats(
            db=db,
            inspection_id=response["inspection_id"],
            filename=file.filename,
            image_width=img.shape[1],
            image_height=img.shape[0],
            confidence_threshold=confidence,
            model_name=selected_model_name,
            model_version=selected_model_version,
            total_defects=total_defects,
            inspection_status=inspection_status,
            severity_counts=severity_counts,
            detections=detections,
            result_image_path=result_image_path,
            upload_path=upload_path,
            processing_time=time.time() - start_time,
            operator_id=current_user.id,
            stats_map=stats_map,
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")


def _validate_detection_params(confidence: float, iou: float, imgsz: int) -> None:
    if not 0.0 <= confidence <= 1.0:
        raise HTTPException(
            status_code=422, detail="confidence must be between 0.0 and 1.0"
        )

    if not 0.0 <= iou <= 1.0:
        raise HTTPException(status_code=422, detail="iou must be between 0.0 and 1.0")

    if imgsz < 320 or imgsz > 4096:
        raise HTTPException(
            status_code=422, detail="imgsz must be between 320 and 4096"
        )

    if imgsz % 32 != 0:
        raise HTTPException(status_code=422, detail="imgsz must be a multiple of 32")
