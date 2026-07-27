import json
import logging
from pathlib import Path

from ultralytics import YOLO

logger = logging.getLogger(__name__)


class ModelManager:
    """Управление несколькими моделями"""

    def __init__(self, models_config_path: str):
        self.models = {}
        self.load_models(models_config_path)

    def load_models(self, config_path: str):
        """Загрузка всех моделей из конфига"""
        with open(config_path, "r") as f:
            config = json.load(f)

        for model_name, model_info in config["models"].items():
            model_path = model_info["path"]
            if Path(model_path).exists():
                self.models[model_name] = {
                    "model": YOLO(model_path),
                    "version": model_info["version"],
                    "description": model_info.get("description", ""),
                    "metrics": model_info.get("metrics", {}),
                    "is_active": model_info.get("is_active", True),
                }
                logger.info("Loaded model %s (v%s)", model_name, model_info["version"])

    def predict(self, image, model_name: str, **kwargs):
        """Предсказание с конкретной моделью"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")

        model = self.models[model_name]["model"]
        return model(image, **kwargs)

    def compare_models(self, image, model_names: list[str] | None = None, **kwargs):
        """Сравнение результатов нескольких моделей"""
        if model_names is None:
            model_names = [
                name for name, info in self.models.items() if info["is_active"]
            ]

        results = {}

        for model_name in model_names:
            if model_name in self.models:
                model_results = self.predict(image, model_name, **kwargs)

                detections = []
                for r in model_results:
                    for box in r.boxes:
                        detections.append(
                            {
                                "class": self.models[model_name]["model"].names[
                                    int(box.cls)
                                ],
                                "confidence": float(box.conf),
                                "bbox": box.xyxy[0].tolist(),
                            }
                        )

                results[model_name] = {
                    "detections": detections,
                    "count": len(detections),
                    "version": self.models[model_name]["version"],
                }

        return results

    def get_model_info(self, model_name: str = None):
        """Получить информацию о модели(ях)"""
        if model_name:
            return self.models.get(model_name)
        return {
            name: {k: v for k, v in info.items() if k != "model"}
            for name, info in self.models.items()
        }
