
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.jwt_handler import get_current_user
from src.database.database import get_db
from src.database.models import Inspection, User

router = APIRouter(prefix="/history", tags=["View history"])


@router.get("/")
async def get_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получите историю проверок"""

    inspections = (
        db.query(Inspection)
        .order_by(Inspection.timestamp.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return {
        "total": db.query(Inspection).count(),
        "limit": limit,
        "offset": offset,
        "inspections": [
            {
                "id": i.id,
                "timestamp": i.timestamp.isoformat(),
                "filename": i.filename,
                "total_defects": i.total_defects,
                "status": i.status,
            }
            for i in inspections
        ],
    }


@router.get("/{inspection_id}")
async def get_inspection_detail(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получите детальную информацию о проверке"""

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    return {
        "id": inspection.id,
        "timestamp": inspection.timestamp.isoformat(),
        "filename": inspection.filename,
        "image_width": inspection.image_width,
        "image_height": inspection.image_height,
        "confidence_threshold": inspection.confidence_threshold,
        "total_defects": inspection.total_defects,
        "status": inspection.status,
        "severity_breakdown": inspection.severity_breakdown,
        "detections": inspection.detections,
        "result_image_path": inspection.result_image_path,
        "original_image_path": inspection.original_image_path,
        "processing_time": round(inspection.processing_time, 2),
        "operator_id": inspection.operator_id,
        "notes": inspection.notes,
    }
