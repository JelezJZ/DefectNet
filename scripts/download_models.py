#!/usr/bin/env python3
"""
Download pretrained YOLO models for DefectNet.

This script downloads the required YOLO11 pretrained models from Ultralytics.
Run this after cloning the repository to get the model weights.

Usage:
    python scripts/download_models.py
"""

import os
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    print("Installing ultralytics...")
    os.system("pip install ultralytics")
    from ultralytics import YOLO


# Models to download
MODELS = {
    "yolo11n.pt": "nano - smallest and fastest",
    "yolo11s.pt": "small - balanced performance",
    "yolo11m.pt": "medium - higher accuracy",
    "yolo11l.pt": "large - best accuracy, slower",
}

# Also fine-tuned model
BEST_MODEL = "best.pt"


def download_model(model_name: str, output_dir: Path) -> Path:
    """Download a YOLO model from Ultralytics."""
    output_path = output_dir / model_name
    if output_path.exists():
        print(f"✓ {model_name} already exists")
        return output_path

    print(f"Downloading {model_name}...")
    try:
        # Download from Ultralytics
        model = YOLO(model_name)
        # The model is cached by ultralytics, copy to our directory
        cache_path = Path.home() / ".config" / "Ultralytics" / model_name
        if cache_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(cache_path, output_path)
            print(f"✓ {model_name} downloaded successfully")
        else:
            # Alternative: download directly
            model.export(format="torchscript")  # This ensures download
            print(f"⚠ {model_name} - manual download may be needed")
    except Exception as e:
        print(f"✗ Error downloading {model_name}: {e}")
        return None

    return output_path


def main():
    """Download all required models."""
    print("=" * 60)
    print("DefectNet - Model Download Script")
    print("=" * 60)

    # Create directories
    pretrained_dir = Path(__file__).parent.parent / "models" / "pretrained"
    models_dir = Path(__file__).parent.parent / "src" / "models"

    pretrained_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nDownloading pretrained models to: {pretrained_dir}\n")

    # Download pretrained models
    for model_name, description in MODELS.items():
        print(f"[{description}]")
        download_model(model_name, pretrained_dir)
        print()

    print("\n" + "=" * 60)
    print("Models downloaded successfully!")
    print("=" * 60)
    print(f"\nPretrained models location: {pretrained_dir}")
    print(f"Training outputs location: {models_dir}")
    print("\nNote: best.pt will be created automatically during training.")


if __name__ == "__main__":
    main()
