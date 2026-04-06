from fastapi import APIRouter, UploadFile, File, Depends
from typing import List, Dict
import numpy as np
import cv2
from src.models.model_manager import ModelManager
from src.database.models import User
from src.auth.jwt_handler import get_current_user

router = APIRouter(prefix="/models", tags=["Model Management"])

# Инициализация менеджера
model_manager = ModelManager("src/models/models_config.json")

@router.get("/list")
async def list_models(current_user: User = Depends(get_current_user)):
    """Список всех доступных моделей"""
    return model_manager.get_model_info()

@router.post("/compare")
async def compare_models(
    file: UploadFile = File(...),
    models: List[str] = None,
    confidence: float = 0.25,
    current_user: User = Depends(get_current_user)
):
    """Сравнение результатов разных моделей на одном изображении"""
    
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    results = model_manager.compare_models(img, models, conf=confidence)
    
    # Анализ различий
    analysis = {
        'comparison': results,
        'summary': {
            'total_models_compared': len(results),
            'detection_agreement': calculate_agreement(results),
            'recommendations': generate_recommendations(results)
        }
    }
    
    return analysis

def calculate_agreement(results: Dict) -> Dict:
    """Вычислить степень согласованности между моделями"""
    model_names = list(results.keys())
    
    if len(model_names) < 2:
        return {'agreement_score': 1.0}
    
    # Упрощённый подсчёт - сравнение количества детекций
    counts = [results[name]['count'] for name in model_names]
    avg_count = np.mean(counts)
    std_count = np.std(counts)
    
    agreement_score = 1.0 - min(std_count / (avg_count + 1), 1.0)
    
    return {
        'agreement_score': round(agreement_score, 3),
        'avg_detections': round(avg_count, 2),
        'std_detections': round(std_count, 2)
    }

def generate_recommendations(results: Dict) -> List[str]:
    """Генерация рекомендации на основе сравнения"""
    recommendations = []
    
    counts = [info['count'] for info in results.values()]
    
    if max(counts) - min(counts) > 5:
        recommendations.append("Большая разница в количестве детекций между моделями")
    
    if all(c == 0 for c in counts):
        recommendations.append("Ни одна модель не обнаружила дефектов")
    
    return recommendations
