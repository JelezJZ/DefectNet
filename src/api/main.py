from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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
model = YOLO('/home/jelez/projects/DefectNet/runs/detect/train6/weights/best.pt')

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
    
    return {
        "detections": detections,
        "count": len(detections)
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}