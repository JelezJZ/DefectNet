from datetime import datetime


def build_detection_response(
    inspection_id: str,
    filename: str,
    image_width: int,
    image_height: int,
    confidence_threshold: float,
    model_name: str,
    model_version: str,
    total_defects: int,
    inspection_status: str,
    severity_counts: dict,
    detections: list,
    result_image_url,
) -> dict:
    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "inspection_id": inspection_id,
        "image_info": {
            "filename": filename,
            "width": image_width,
            "height": image_height,
        },
        "detection_params": {
            "confidence_threshold": confidence_threshold,
            "model": model_name,
            "model_version": model_version,
        },
        "results": {
            "total_defects": total_defects,
            "status": inspection_status,
            "severity_breakdown": severity_counts,
            "detections": detections,
        },
        "result_image": result_image_url,
    }
