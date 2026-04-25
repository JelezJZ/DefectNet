from pathlib import Path
import json

from fastapi import HTTPException
from ultralytics import YOLO


def discover_model_paths(default_model_path: str, models_config_path: Path) -> dict:
    paths = {"default": default_model_path}

    if not models_config_path.exists():
        return paths

    try:
        with open(models_config_path, "r", encoding="utf-8") as file_obj:
            config = json.load(file_obj)
    except Exception:
        return paths

    for model_name, model_info in config.get("models", {}).items():
        model_path = model_info.get("path")
        if not model_path:
            continue
        if Path(model_path).exists():
            paths[model_name] = model_path

    return paths


def get_or_load_model(model_name: str, model_cache: dict, model_paths: dict):
    selected_name = model_name or "default"

    if selected_name in model_cache:
        return model_cache[selected_name], selected_name

    if selected_name not in model_paths:
        available = sorted(model_paths.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{selected_name}'. Available models: {available}",
        )

    model_path = model_paths[selected_name]
    model_cache[selected_name] = YOLO(model_path)
    return model_cache[selected_name], selected_name
