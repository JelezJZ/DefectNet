from datetime import datetime
import uuid


def build_detection_response(
    filename: str,
    image_width: int,
    image_height: int,
    confidence_threshold: float,
    model_name: str,
    total_defects: int,
    inspection_status: str,
    severity_counts: dict,
    detections: list,
    result_image_url,
) -> dict:
    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "inspection_id": str(uuid.uuid4()),
        "image_info": {
            "filename": filename,
            "width": image_width,
            "height": image_height,
        },
        "detection_params": {
            "confidence_threshold": confidence_threshold,
            "model": model_name,
        },
        "results": {
            "total_defects": total_defects,
            "status": inspection_status,
            "severity_breakdown": severity_counts,
            "detections": detections,
        },
        "result_image": result_image_url,
    }
