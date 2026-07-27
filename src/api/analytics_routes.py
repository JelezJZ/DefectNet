from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.auth.jwt_handler import get_current_user
from src.database.database import get_db
from src.database.models import Inspection, User

router = APIRouter(tags=["Analitics"])


@router.get("/dashboard")
async def dashboard():
    """Страница дашборда"""

    from src.api.main import FRONTEND_DIR

    dashboard_path = FRONTEND_DIR / "dashboard.html"
    if dashboard_path.exists():
        return HTMLResponse(content=dashboard_path.read_text())
    return {"error": "Dashboard not found"}


@router.get("/analytics/dashboard")
async def get_analytics(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Дашборд с аналитикой"""

    total_inspections = db.query(Inspection).count()

    # Дефекты по типам
    all_inspections = db.query(Inspection).all()
    defect_counts = {}

    for insp in all_inspections:
        if insp.detections:
            for det in insp.detections:
                defect_type = det.get("class")
                defect_counts[defect_type] = defect_counts.get(defect_type, 0) + 1

    # Pass rate
    passed = db.query(Inspection).filter(Inspection.status == "passed").count()
    pass_rate = (passed / total_inspections * 100) if total_inspections > 0 else 0

    return {
        "total_inspections": total_inspections,
        "total_defects_found": sum(defect_counts.values()),
        "defect_breakdown": defect_counts,
        "pass_rate": round(pass_rate, 2),
        "status_breakdown": {
            "passed": db.query(Inspection)
            .filter(Inspection.status == "passed")
            .count(),
            "warning": db.query(Inspection)
            .filter(Inspection.status == "warning")
            .count(),
            "failed": db.query(Inspection)
            .filter(Inspection.status == "failed")
            .count(),
        },
    }
