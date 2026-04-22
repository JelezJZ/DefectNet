from datetime import datetime
import logging

from sqlalchemy.orm import Session

from src.database.models import DefectStatistics, Inspection


logger = logging.getLogger(__name__)


def save_inspection_and_stats(
    db: Session,
    inspection_id: str,
    filename: str,
    image_width: int,
    image_height: int,
    confidence_threshold: float,
    total_defects: int,
    inspection_status: str,
    severity_counts: dict,
    detections: list,
    result_image_path,
    upload_path,
    processing_time: float,
    operator_id: str,
    stats_map: dict,
) -> None:
    try:
        inspection = Inspection(
            id=inspection_id,
            timestamp=datetime.now(),
            filename=filename,
            image_width=image_width,
            image_height=image_height,
            confidence_threshold=confidence_threshold,
            total_defects=total_defects,
            status=inspection_status,
            severity_breakdown=severity_counts,
            detections=detections,
            result_image_path=str(result_image_path) if result_image_path else None,
            original_image_path=str(upload_path),
            processing_time=processing_time,
            operator_id=operator_id,
        )

        db.add(inspection)

        for defect_type, data in stats_map.items():
            stat_entry = DefectStatistics(
                date=datetime.now(),
                defect_type=defect_type,
                count=data["count"],
                avg_confidence=data["total_conf"] / data["count"],
            )
            db.add(stat_entry)

        db.commit()
        db.refresh(inspection)
    except Exception as error:
        db.rollback()
        logger.exception("Database error while saving inspection: %s", error)
