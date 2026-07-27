import csv
import io
import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy.orm import Session

from src.auth.jwt_handler import get_current_user
from src.database.database import get_db
from src.database.models import Inspection, User
from src.reports.generator import ReportGenerator

router = APIRouter(prefix="/export", tags=["Export files"])


@router.get("/pdf/{inspection_id}")
async def export_pdf_report(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт отчёта в PDF"""

    output_dir = os.getenv("REPORTS_DIR", "storage/reports")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Преобразовываем в формат для отчёта
    report_data = {
        "inspection_id": inspection.id,
        "timestamp": inspection.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "image_info": {
            "filename": inspection.filename,
            "width": inspection.image_width,
            "height": inspection.image_height,
        },
        "results": {
            "status": inspection.status,
            "total_defects": inspection.total_defects,
            "detections": inspection.detections,
        },
    }

    # Генерируем PDF
    output_path = f"storage/reports/inspection_{inspection_id}.pdf"
    generator = ReportGenerator()
    generator.generate_inspection_report(report_data, output_path)

    return FileResponse(output_path, filename=f"report_{inspection_id}.pdf")


@router.get("/json/{inspection_id}")
async def export_inspection_json(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт одной проверки в JSON-файл"""

    output_dir = os.getenv("EXPORTS_DIR", "storage/exports")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    payload = {
        "inspection_id": inspection.id,
        "timestamp": inspection.timestamp.isoformat() if inspection.timestamp else None,
        "image_info": {
            "filename": inspection.filename,
            "width": inspection.image_width,
            "height": inspection.image_height,
        },
        "detection_params": {
            "confidence_threshold": inspection.confidence_threshold,
        },
        "results": {
            "status": inspection.status,
            "total_defects": inspection.total_defects,
            "severity_breakdown": inspection.severity_breakdown or {},
            "detections": inspection.detections or [],
        },
        "meta": {
            "processing_time": inspection.processing_time,
            "operator_id": inspection.operator_id,
            "original_image_path": inspection.original_image_path,
            "result_image_path": inspection.result_image_path,
        },
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"inspection_{inspection_id}_{timestamp}.json"
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    return FileResponse(
        output_path,
        media_type="application/json",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/image/{inspection_id}")
async def export_result_image(
    inspection_id: str,
    format: str = "jpeg",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт изображения результата в PNG/JPEG"""

    image_format = format.strip().lower()
    if image_format not in {"png", "jpeg", "jpg"}:
        raise HTTPException(
            status_code=422, detail="format must be one of: png, jpeg, jpg"
        )

    output_dir = os.getenv("EXPORTS_DIR", "storage/exports")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if not inspection.result_image_path:
        raise HTTPException(
            status_code=404, detail="No result image for this inspection"
        )

    source_path = Path(inspection.result_image_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Result image file not found")

    normalized_format = "jpeg" if image_format == "jpg" else image_format
    extension = "jpg" if normalized_format == "jpeg" else "png"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"inspection_{inspection_id}_{timestamp}.{extension}"
    output_path = Path(output_dir) / filename

    with Image.open(source_path) as img:
        export_image = img.convert("RGB") if normalized_format == "jpeg" else img
        export_image.save(output_path, format=normalized_format.upper())

    media_type = "image/jpeg" if normalized_format == "jpeg" else "image/png"
    return FileResponse(
        str(output_path),
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/csv")
async def export_inspections_csv(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Экспорт всех проверок в CSV"""

    output_dir = os.getenv("EXPORTS_DIR", "storage/exports")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    inspections = db.query(Inspection).order_by(Inspection.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    writer.writerow(
        [
            "ID",
            "Дата и время",
            "Имя файла",
            "Ширина изображения",
            "Высота изображения",
            "Порог уверенности",
            "Всего дефектов",
            "Статус",
            "Критические",
            "Средние",
            "Низкие",
            "Время обработки (с)",
            "Оператор ID",
            "Примечания",
        ]
    )

    for insp in inspections:
        severity = insp.severity_breakdown if insp.severity_breakdown else {}
        writer.writerow(
            [
                insp.id,
                insp.timestamp.strftime("%Y-%m-%d %H:%M:%S") if insp.timestamp else "",
                insp.filename,
                insp.image_width,
                insp.image_height,
                insp.confidence_threshold,
                insp.total_defects,
                insp.status,
                severity.get("critical", 0),
                severity.get("medium", 0),
                severity.get("low", 0),
                insp.processing_time,
                insp.operator_id or "",
                insp.notes or "",
            ]
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"inspections_export_{timestamp}.csv"
    output_path = os.path.join(output_dir, filename)

    output.seek(0)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(output.getvalue())

    return FileResponse(
        output_path,
        media_type="text/csv",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
