from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO
from pathlib import Path
import uuid
from datetime import datetime
from typing import List
from src.database.models import Inspection, get_db, User
import time
from sqlalchemy.orm import Session
from src.reports.generator import ReportGenerator
import os
from src.api.auth_routes import router as auth_router
from src.api.websocket_routes import router as websocket_router
from src.api.batch_routes import router as batch_router
from src.api.models_routes import router as model_router
from src.auth.jwt_handler import get_current_user
import csv
import io
import logging
from dotenv import load_dotenv
from collections import defaultdict, deque
from threading import Lock
from src.services.detection_pipeline import (
    validate_image_upload,
    save_uploaded_image,
    decode_image,
    run_inference,
    build_detections,
    save_result_visualization,
    get_inspection_status,
    build_defect_stats,
)
from src.services.detection_response import build_detection_response
from src.services.inspection_persistence import save_inspection_and_stats
from src.services.model_registry import discover_model_paths, get_or_load_model
from src.core.logging_config import setup_logging

# Load environment variables
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PCB Defect Detection API",
    description="Автоматическое обнаружение дефектов печатных плат",
    version="1.0.0"
)

# CORS
environment = os.getenv("ENVIRONMENT", "development").strip().lower()
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in raw_allowed_origins.split(",") if origin.strip()]

if environment == "production" and "*" in allowed_origins:
    raise RuntimeError("ALLOWED_ORIGINS cannot contain '*' in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
rate_limit_window_seconds = 60
rate_limit_hits = defaultdict(deque)
rate_limit_lock = Lock()


@app.middleware("http")
async def ip_rate_limit_middleware(request: Request, call_next):
    path = request.url.path

    if (
        path.startswith("/css/")
        or path.startswith("/js/")
        or path.startswith("/results/")
        or path.startswith("/uploads/")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path.startswith("/openapi.json")
        or path.startswith("/health")
    ):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    with rate_limit_lock:
        timestamps = rate_limit_hits[client_ip]
        while timestamps and now - timestamps[0] > rate_limit_window_seconds:
            timestamps.popleft()

        if len(timestamps) >= rate_limit_per_minute:
            retry_after = max(1, int(rate_limit_window_seconds - (now - timestamps[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Max {rate_limit_per_minute} requests per minute per IP"
                },
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)

    return await call_next(request)

# Статические файлы (frontend)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

app.include_router(auth_router)
app.include_router(websocket_router)
app.include_router(batch_router)
app.include_router(model_router)

# Глобальная переменная для модели
model = None
model_cache = {}
available_model_paths = {}

# Storage directories from env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / os.getenv("STORAGE_DIR", "storage")
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "storage/uploads")
RESULTS_DIR = BASE_DIR / os.getenv("RESULTS_DIR", "storage/results")

UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Конфигурация
DEFECT_INFO = {
    'mouse_bite': {
        'name_ru': 'Мышиный укус',
        'severity': 'medium',
        'description': 'Неровные края на печатной плате'
    },
    'spur': {
        'name_ru': 'Выступ',
        'severity': 'low',
        'description': 'Выступ на проводнике'
    },
    'missing_hole': {
        'name_ru': 'Отсутствующее отверстие',
        'severity': 'critical',
        'description': 'Отверстие не просверлено или отсутствует'
    },
    'short': {
        'name_ru': 'Короткое замыкание',
        'severity': 'critical',
        'description': 'Нежелательное соединение проводников'
    },
    'open_circuit': {
        'name_ru': 'Разрыв цепи',
        'severity': 'critical',
        'description': 'Разрыв проводника'
    },
    'spurious_copper': {
        'name_ru': 'Лишняя медь',
        'severity': 'medium',
        'description': 'Остатки меди на плате'
    }
}

@app.on_event("startup")
async def load_model():
    """Загрузите модель при старте приложения"""
    global model, model_cache, available_model_paths
    model_path = os.getenv("MODEL_PATH", "src/models/best.pt")

    if not Path(model_path).exists():
        raise RuntimeError(f"Model not found at {model_path}")

    model = YOLO(model_path)
    model_cache = {"default": model}
    available_model_paths = discover_model_paths(
        default_model_path=model_path,
        models_config_path=BASE_DIR / "src" / "models" / "models_config.json",
    )
    logger.info("Model loaded from %s", model_path)

@app.get("/")
async def root():
    """Главная страница API"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return {
        "message": "PCB Defect Detection API",
        "version": "1.0.0",
        "status": "running",
        "model_loaded": model is not None
    }

@app.get("/dashboard")
async def dashboard():
    """Страница дашборда"""
    dashboard_path = FRONTEND_DIR / "dashboard.html"
    if dashboard_path.exists():
        return HTMLResponse(content=dashboard_path.read_text())
    return {"error": "Dashboard not found"}

@app.get("/health")
async def health_check():
    """Проверка работоспособности"""
    return {
        "status": "healthy",
        "model_status": "loaded" if model else "not_loaded"
    }

async def _process_detection(
    file: UploadFile,
    confidence: float,
    iou_threshold: float,
    image_size: int,
    model_name: str,
    save_image: bool,
    db: Session,
    current_user: User
):
    """
    Внутренняя функция для детекции дефектов (без FastAPI зависимостей)
    """

    start_time = time.time()

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
        upload_path = save_uploaded_image(contents, file.filename, UPLOAD_DIR)
        img = decode_image(contents)

        augment = os.getenv("AUGMENT", "True").lower() == "true"

        results = run_inference(selected_model, img, confidence, image_size, iou_threshold, augment)
        detections, severity_counts = build_detections(results, selected_model.names, DEFECT_INFO)
        total_defects = len(detections)
        result_image_path, result_image_url = save_result_visualization(
            results, detections, save_image, RESULTS_DIR
        )
        inspection_status = get_inspection_status(severity_counts)

        response = build_detection_response(
            filename=file.filename,
            image_width=img.shape[1],
            image_height=img.shape[0],
            confidence_threshold=confidence,
            model_name=selected_model_name,
            total_defects=total_defects,
            inspection_status=inspection_status,
            severity_counts=severity_counts,
            detections=detections,
            result_image_url=result_image_url,
        )

        stats_map = build_defect_stats(detections)
        save_inspection_and_stats(
            db=db,
            inspection_id=response['inspection_id'],
            filename=file.filename,
            image_width=img.shape[1],
            image_height=img.shape[0],
            confidence_threshold=confidence,
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
        raise HTTPException(status_code=422, detail="confidence must be between 0.0 and 1.0")

    if not 0.0 <= iou <= 1.0:
        raise HTTPException(status_code=422, detail="iou must be between 0.0 and 1.0")

    if imgsz < 320 or imgsz > 4096:
        raise HTTPException(status_code=422, detail="imgsz must be between 320 and 4096")

    if imgsz % 32 != 0:
        raise HTTPException(status_code=422, detail="imgsz must be a multiple of 32")

@app.post("/detect")
async def detect_defects(
    file: UploadFile = File(...),
    confidence: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 1024,
    model_name: str = "default",
    save_image: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    return await _process_detection(file, confidence, iou, imgsz, model_name, save_image, db, current_user)

@app.post("/batch-detect")
async def batch_detect(
    files: List[UploadFile] = File(...),
    confidence: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 1024,
    model_name: str = "default",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Пакетная обработка нескольких изображений"""

    max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "20"))
    if len(files) > max_batch_size:
        raise HTTPException(status_code=400, detail=f"Maximum {max_batch_size} images per batch")

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
            results_list.append({
                'filename': file.filename,
                'status': 'success',
                'data': result
            })
        except Exception as e:
            results_list.append({
                'filename': file.filename,
                'status': 'error',
                'error': str(e)
            })

    return {
        'batch_id': str(uuid.uuid4()),
        'total_images': len(files),
        'processed': len(results_list),
        'results': results_list
    }

@app.get("/results/{filename}")
async def get_result_image(filename: str):
    """Получите изображение с результатами"""
    file_path = RESULTS_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path)

@app.get("/uploads/{filename}")
async def get_original_image(filename: str):
    """Получите оригинальное изображение"""
    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path)

@app.get("/defect-info")
async def get_defect_info():
    """Получите информацию о типах дефектов"""
    return DEFECT_INFO


@app.get("/models/available")
async def get_available_models(current_user: User = Depends(get_current_user)):
    """Список доступных моделей для endpoint /detect"""
    return {
        "models": sorted(available_model_paths.keys())
    }

@app.get("/statistics")
async def get_statistics():
    """Статистика по сохранённым результатам"""
    # Здесь можно добавить подключение к БД для реальной статистики
    # Пока заглушка
    return {
        'total_inspections': 0,
        'total_defects_found': 0,
        'defect_breakdown': {},
        'pass_rate': 0.0
    }

@app.get("/history")
async def get_history(limit: int = 50, offset: int = 0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Получите историю проверок"""

    inspections = db.query(Inspection)\
        .order_by(Inspection.timestamp.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()

    return {
        'total': db.query(Inspection).count(),
        'limit': limit,
        'offset': offset,
        'inspections': [
            {
                'id': i.id,
                'timestamp': i.timestamp.isoformat(),
                'filename': i.filename,
                'total_defects': i.total_defects,
                'status': i.status
            }
            for i in inspections
        ]
    }

@app.get("/history/{inspection_id}")
async def get_inspection_detail(inspection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Получите детальную информацию о проверке"""

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    return {
        'id': inspection.id,
        'timestamp': inspection.timestamp.isoformat(),
        'filename': inspection.filename,
        'image_width': inspection.image_width,
        'image_height': inspection.image_height,
        'confidence_threshold': inspection.confidence_threshold,
        'total_defects': inspection.total_defects,
        'status': inspection.status,
        'severity_breakdown': inspection.severity_breakdown,
        'detections': inspection.detections,
        'result_image_path': inspection.result_image_path,
        'original_image_path': inspection.original_image_path,
        'processing_time': round(inspection.processing_time, 2),
        'operator_id': inspection.operator_id,
        'notes': inspection.notes
    }

@app.get("/analytics/dashboard")
async def get_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Дашборд с аналитикой"""

    total_inspections = db.query(Inspection).count()
    
    # Дефекты по типам
    all_inspections = db.query(Inspection).all()
    defect_counts = {}
    
    for insp in all_inspections:
        if insp.detections:
            for det in insp.detections:
                defect_type = det.get('class')
                defect_counts[defect_type] = defect_counts.get(defect_type, 0) + 1
    
    # Pass rate
    passed = db.query(Inspection).filter(Inspection.status == 'passed').count()
    pass_rate = (passed / total_inspections * 100) if total_inspections > 0 else 0
    
    return {
        'total_inspections': total_inspections,
        'total_defects_found': sum(defect_counts.values()),
        'defect_breakdown': defect_counts,
        'pass_rate': round(pass_rate, 2),
        'status_breakdown': {
            'passed': db.query(Inspection).filter(Inspection.status == 'passed').count(),
            'warning': db.query(Inspection).filter(Inspection.status == 'warning').count(),
            'failed': db.query(Inspection).filter(Inspection.status == 'failed').count()
        }
    }

@app.get("/export/pdf/{inspection_id}")
async def export_pdf_report(inspection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Экспорт отчёта в PDF"""

    output_dir = os.getenv("REPORTS_DIR", "storage/reports")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Преобразовываем в формат для отчёта
    report_data = {
        'inspection_id': inspection.id,
        'timestamp': inspection.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'image_info': {
            'filename': inspection.filename,
            'width': inspection.image_width,
            'height': inspection.image_height
        },
        'results': {
            'status': inspection.status,
            'total_defects': inspection.total_defects,
            'detections': inspection.detections
        }
    }
    
    # Генерируем PDF
    output_path = f"storage/reports/inspection_{inspection_id}.pdf"
    generator = ReportGenerator()
    generator.generate_inspection_report(report_data, output_path)

    return FileResponse(output_path, filename=f"report_{inspection_id}.pdf")

@app.get("/export/csv")
async def export_inspections_csv(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Экспорт всех проверок в CSV"""

    output_dir = os.getenv("EXPORTS_DIR", "storage/exports")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    inspections = db.query(Inspection).order_by(Inspection.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    
    writer.writerow([
        'ID',
        'Дата и время',
        'Имя файла',
        'Ширина изображения',
        'Высота изображения',
        'Порог уверенности',
        'Всего дефектов',
        'Статус',
        'Критические',
        'Средние',
        'Низкие',
        'Время обработки (с)',
        'Оператор ID',
        'Примечания'
    ])
    
    for insp in inspections:
        severity = insp.severity_breakdown if insp.severity_breakdown else {}
        writer.writerow([
            insp.id,
            insp.timestamp.strftime('%Y-%m-%d %H:%M:%S') if insp.timestamp else '',
            insp.filename,
            insp.image_width,
            insp.image_height,
            insp.confidence_threshold,
            insp.total_defects,
            insp.status,
            severity.get('critical', 0),
            severity.get('medium', 0),
            severity.get('low', 0),
            insp.processing_time,
            insp.operator_id or '',
            insp.notes or ''
        ])
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"inspections_export_{timestamp}.csv"
    output_path = os.path.join(output_dir, filename)
    
    output.seek(0)
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(output.getvalue())
    
    return FileResponse(
        output_path,
        media_type="text/csv",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.api.main:app", host=host, port=port, reload=True)
    
    # Команда запуска:
    # export PYTHONPATH=$PYTHONPATH:$(pwd)/src  # Для Linux/macOS
    # или для Windows (PowerShell): $env:PYTHONPATH += ";$pwd\src"=
    # python -m src.api.main
