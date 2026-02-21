# src/api/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path
import io
from PIL import Image
import uuid
from datetime import datetime
from typing import List, Optional
import json

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
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")

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
    model_path = "../models/best.pt"
    
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
    save_image: bool = True
):
    """
    Основной endpoint для детекции дефектов
    
    Args:
        file: Изображение печатной платы
        confidence: Порог уверенности (0.0-1.0)
        save_image: Сохранять ли изображение с результатами
    """
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Валидация типа файла
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Прочитайте изображение
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Запустите детекцию
        results = model(img, conf=confidence)
        
        # Обработайте результаты
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
        
        # Сохраните изображение с результатами
        result_image_path = None
        if save_image and len(detections) > 0:
            result_img = results[0].plot()
            
            # Генерируйте уникальное имя
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_filename = f"result_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            result_image_path = RESULTS_DIR / result_filename
            
            cv2.imwrite(str(result_image_path), result_img)
        
        # Определите статус проверки
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
            # Вызовите обычный detect для каждого файла
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)