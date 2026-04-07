from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path
import uuid
from datetime import datetime
from typing import List
from src.database.models import Inspection, DefectStatistics, get_db, User
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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="PCB Defect Detection API",
    description="Автоматическое обнаружение дефектов печатных плат",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    global model
    model_path = os.getenv("MODEL_PATH", "src/models/best.pt")

    if not Path(model_path).exists():
        raise RuntimeError(f"Model not found at {model_path}")

    model = YOLO(model_path)
    print(f"✅ Model loaded from {model_path}")

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

    # Валидация типа файла
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        # Читаем изображение
        contents = await file.read()

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        # Сохраняем расширение оригинального файла
        extension = Path(file.filename).suffix or ".jpg"
        upload_filename = f"upload_{timestamp_str}_{unique_id}{extension}"
        upload_path = UPLOAD_DIR / upload_filename

        # Записываем байты из памяти на диск
        with open(upload_path, "wb") as f:
            f.write(contents)

        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Запускаем детекцию
        image_size = int(os.getenv("IMAGE_SIZE", "1024"))
        iou_threshold = float(os.getenv("IOU_THRESHOLD", "0.45"))
        augment = os.getenv("AUGMENT", "True").lower() == "true"
        
        results = model(img, conf=confidence, imgsz=image_size, iou=iou_threshold, augment=augment)

        # Обрабатываем результаты
        detections = []
        total_defects = 0
        severity_counts = {'critical': 0, 'medium': 0, 'low': 0}

        for r in results:
            for box in r.boxes:
                class_id = int(box.cls)
                class_name = model.names[class_id]
                conf = float(box.conf)
                bbox = box.xyxy[0].tolist()

                defect_info = DEFECT_INFO.get(class_name, {})
                severity = defect_info.get('severity', 'unknown')

                detections.append({
                    'id': str(uuid.uuid4()),
                    'class': class_name,
                    'class_ru': defect_info.get('name_ru', class_name),
                    'confidence': round(conf, 3),
                    'bbox': {
                        'x1': round(bbox[0], 2),
                        'y1': round(bbox[1], 2),
                        'x2': round(bbox[2], 2),
                        'y2': round(bbox[3], 2)
                    },
                    'severity': severity,
                    'description': defect_info.get('description', '')
                })

                total_defects += 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Сохраняем изображение с результатами
        result_image_path = None
        if save_image and len(detections) > 0:
            result_img = results[0].plot()

            # Генерируем уникальное имя
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_filename = f"result_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            result_image_path = RESULTS_DIR / result_filename

            cv2.imwrite(str(result_image_path), result_img)

        # Определяем статус проверки
        inspection_status = "passed"
        if severity_counts.get('critical', 0) > 0:
            inspection_status = "failed"
        elif severity_counts.get('medium', 0) > 0:
            inspection_status = "warning"

        response = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'inspection_id': str(uuid.uuid4()),
            'image_info': {
                'filename': file.filename,
                'width': img.shape[1],
                'height': img.shape[0]
            },
            'detection_params': {
                'confidence_threshold': confidence,
                'model': 'YOLO11m'
            },
            'results': {
                'total_defects': total_defects,
                'status': inspection_status,
                'severity_breakdown': severity_counts,
                'detections': detections
            },
            'result_image': f"/results/{result_filename}" if result_image_path else None
        }

        try:
            inspection = Inspection(
                id=response['inspection_id'],
                timestamp=datetime.now(),
                filename=file.filename,
                image_width=img.shape[1],
                image_height=img.shape[0],
                confidence_threshold=confidence,
                total_defects=total_defects,
                status=inspection_status,
                severity_breakdown=severity_counts,
                detections=detections,
                result_image_path=str(result_image_path) if result_image_path else None,
                original_image_path=str(upload_path),
                processing_time=time.time() - start_time,
                operator_id=current_user.id
            )

            db.add(inspection)

            # Группируем детекции из текущего запроса по типам
            stats_map = {} # { 'missing_component': {'count': 0, 'total_conf': 0.0} }

            for det in detections:
                d_type = det['class']
                conf = det['confidence']
                if d_type not in stats_map:
                    stats_map[d_type] = {'count': 0, 'total_conf': 0.0}
                stats_map[d_type]['count'] += 1
                stats_map[d_type]['total_conf'] += conf

            # Записываем агрегированные данные в БД
            for d_type, data in stats_map.items():
                # Ищем, есть ли уже статистика по этому типу за сегодня (опционально)
                # Или просто добавляем новую запись для каждой инспекции:
                stat_entry = DefectStatistics(
                    date=datetime.now(),
                    defect_type=d_type,
                    count=data['count'],
                    avg_confidence=data['total_conf'] / data['count']
                )
                db.add(stat_entry)

            db.commit()
            db.refresh(inspection) # Обновляем объект из базы
        except Exception as db_error:
            db.rollback()
            print(f"Database error: {db_error}")

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")

@app.post("/detect")
async def detect_defects(
    file: UploadFile = File(...),
    confidence: float = 0.25,
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
    return await _process_detection(file, confidence, save_image, db, current_user)

@app.post("/batch-detect")
async def batch_detect(
    files: List[UploadFile] = File(...),
    confidence: float = 0.25,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Пакетная обработка нескольких изображений"""

    max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "20"))
    if len(files) > max_batch_size:
        raise HTTPException(status_code=400, detail=f"Maximum {max_batch_size} images per batch")

    results_list = []

    for file in files:
        try:
            # Вызываем внутреннюю функцию detect для каждого файла
            result = await _process_detection(file, confidence, save_image=True, db=db, current_user=current_user)
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