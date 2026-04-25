from datetime import datetime
from pathlib import Path
import uuid

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile


def validate_image_upload(file: UploadFile, contents: bytes, max_upload_size_mb: int) -> None:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    max_upload_size_bytes = max_upload_size_mb * 1024 * 1024
    if len(contents) > max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {max_upload_size_mb} MB",
        )


def save_uploaded_image(contents: bytes, original_filename: str, upload_dir: Path) -> Path:
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    extension = Path(original_filename).suffix or ".jpg"
    upload_filename = f"upload_{timestamp_str}_{unique_id}{extension}"
    upload_path = upload_dir / upload_filename

    with open(upload_path, "wb") as file_obj:
        file_obj.write(contents)

    return upload_path


def decode_image(contents: bytes):
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    return img


def run_inference(model, img, confidence: float, image_size: int, iou_threshold: float, augment: bool):
    return model(img, conf=confidence, imgsz=image_size, iou=iou_threshold, augment=augment)


def build_detections(results, class_names, defect_info: dict):
    detections = []
    severity_counts = {"critical": 0, "medium": 0, "low": 0}

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls)
            class_name = class_names[class_id]
            confidence = float(box.conf)
            bbox = box.xyxy[0].tolist()

            class_info = defect_info.get(class_name, {})
            severity = class_info.get("severity", "unknown")

            detections.append(
                {
                    "id": str(uuid.uuid4()),
                    "class": class_name,
                    "class_ru": class_info.get("name_ru", class_name),
                    "confidence": round(confidence, 3),
                    "bbox": {
                        "x1": round(bbox[0], 2),
                        "y1": round(bbox[1], 2),
                        "x2": round(bbox[2], 2),
                        "y2": round(bbox[3], 2),
                    },
                    "severity": severity,
                    "description": class_info.get("description", ""),
                }
            )

            severity_counts[severity] = severity_counts.get(severity, 0) + 1

    return detections, severity_counts


def save_result_visualization(results, detections: list, save_image: bool, results_dir: Path):
    if not save_image or not detections:
        return None, None

    result_img = results[0].plot()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_filename = f"result_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
    result_path = results_dir / result_filename
    cv2.imwrite(str(result_path), result_img)

    return result_path, f"/results/{result_filename}"


def get_inspection_status(severity_counts: dict) -> str:
    if severity_counts.get("critical", 0) > 0:
        return "failed"
    if severity_counts.get("medium", 0) > 0:
        return "warning"
    return "passed"


def build_defect_stats(detections: list) -> dict:
    stats_map = {}
    for detection in detections:
        defect_type = detection["class"]
        confidence = detection["confidence"]
        if defect_type not in stats_map:
            stats_map[defect_type] = {"count": 0, "total_conf": 0.0}
        stats_map[defect_type]["count"] += 1
        stats_map[defect_type]["total_conf"] += confidence
    return stats_map
