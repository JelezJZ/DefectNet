from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path
import uuid
from datetime import datetime
from typing import List
from src.database.models import SessionLocal, Inspection, DefectStatistics
import time
from sqlalchemy.orm import Session
from src.reports.generator import ReportGenerator
import os

app = FastAPI(
    title="PCB Defect Detection API",
    description="Автоматическое обнаружение дефектов печатных плат",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальная переменная для модели
model = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
RESULTS_DIR = STORAGE_DIR / "results"

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def load_model():
    """Загрузите модель при старте приложения"""
    global model
    model_path = "src/models/best.pt"
    
    if not Path(model_path).exists():
        raise RuntimeError(f"Model not found at {model_path}")
    
    model = YOLO(model_path)
    print(f"✅ Model loaded from {model_path}")

@app.get("/")
async def root():
    """Главная страница API"""
    return {
        "message": "PCB Defect Detection API",
        "version": "1.0.0",
        "status": "running",
        "model_loaded": model is not None
    }

@app.get("/health")
async def health_check():
    """Проверка работоспособности"""
    return {
        "status": "healthy",
        "model_status": "loaded" if model else "not_loaded"
    }

@app.post("/detect")
async def detect_defects(
    file: UploadFile = File(...),
    confidence: float = 0.25,
    save_image: bool = True,
    db: Session = Depends(get_db)
):
    """
    Основной endpoint для детекции дефектов
    
    Args:
        file: Изображение печатной платы
        confidence: Порог уверенности (0.0-1.0)
        save_image: Сохранять ли изображение с результатами
        db: Зависимость БД
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
        results = model(img, conf=confidence, imgsz=1024, iou=0.45, augment=True)
        
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
                processing_time=time.time() - start_time
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
        
        return JSONResponse(content=response)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")

@app.post("/batch-detect")
async def batch_detect(
    files: List[UploadFile] = File(...),
    confidence: float = 0.25
):
    """Пакетная обработка нескольких изображений"""
    
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 images per batch")
    
    results_list = []
    
    for file in files:
        try:
            # Вызываем обычный detect для каждого файла
            result = await detect_defects(file, confidence, save_image=False)
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
async def get_history(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
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

@app.get("/analytics/dashboard")
async def get_analytics(db: Session = Depends(get_db)):
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
async def export_pdf_report(inspection_id: str, db: Session = Depends(get_db)):
    """Экспорт отчёта в PDF"""

    output_dir = "reports"
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
    output_path = f"reports/inspection_{inspection_id}.pdf"
    generator = ReportGenerator()
    generator.generate_inspection_report(report_data, output_path)
    
    return FileResponse(output_path, filename=f"report_{inspection_id}.pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
    
    # Команда запуска:
    # export PYTHONPATH=$PYTHONPATH:$(pwd)/src  # Для Linux/macOS
    # или для Windows (PowerShell): $env:PYTHONPATH += ";$pwd\src"=
    # python -m src.api.main