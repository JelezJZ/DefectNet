from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ultralytics import YOLO
import cv2
import numpy as np
from io import BytesIO

app = FastAPI(title="Defect Detection API")

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Загрузите модель при старте
model = YOLO('/home/jelez/projects/DefectNet/src/models/best.pt')

@app.post("/detect")
async def detect_defects(file: UploadFile = File(...)):
    # Прочитайте изображение
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Предсказание
    results = model(img)
    
    # Форматируйте результаты
    detections = []
    for r in results:
        for box in r.boxes:
            detections.append({
                "class": model.names[int(box.cls)],
                "confidence": float(box.conf),
                "bbox": box.xyxy[0].tolist()
            })
    
    # Отрисовка boxes на изображении
    img_with_boxes = img.copy()
    for detection in detections:
        bbox = detection["bbox"]
        x1, y1, x2, y2 = map(int, bbox)
        
        # Цвет рамки (BGR)
        color = (0, 255, 0)  # Зеленый
        
        # Рисуем прямоугольник
        cv2.rectangle(img_with_boxes, (x1, y1), (x2, y2), color, 2)
        
        # Подготовка текста
        label = f"{detection['class']}: {detection['confidence']:.2f}"
        
        # Рисуем фон для текста
        (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(img_with_boxes, (x1, y1 - text_height - 10), (x1 + text_width, y1), color, -1)
        
        # Рисуем текст
        cv2.putText(img_with_boxes, label, (x1, y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
    # Конвертируем изображение в base64
    _, img_encoded = cv2.imencode('.jpg', img_with_boxes)
    img_base64 = BytesIO(img_encoded.tobytes())
    
    return StreamingResponse(img_base64, media_type="image/jpeg")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}