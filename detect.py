import cv2
from ultralytics import YOLO

model = YOLO("runs/detect/train6/weights/best.pt")
image = cv2.imread("test.jpg")

results = model.predict(source=image, imgsz=640, save=True)