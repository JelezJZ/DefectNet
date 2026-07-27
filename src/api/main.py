import json
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

from src.api.analytics_routes import router as analytics_router
from src.api.auth_routes import router as auth_router
from src.api.batch_routes import router as batch_router
from src.api.detect_routes import router as detect_router
from src.api.export_routes import router as export_router
from src.api.files_routes import router as file_router
from src.api.history_routes import router as history_router
from src.api.models_routes import router as model_router
from src.api.websocket_routes import router as websocket_router
from src.auth.jwt_handler import get_current_user
from src.core.logging_config import setup_logging
from src.database.models import User
from src.services.model_registry import discover_model_paths

# Load environment variables
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загрузите модель при старте приложения"""
    global model, model_cache, available_model_paths, model_versions
    model_path = os.getenv(
        "MODEL_PATH", "models/trained/pcb_defect_detector_v13_best.pt"
    )

    if not Path(model_path).exists():
        raise RuntimeError(f"Model not found at {model_path}")

    model = YOLO(model_path)
    model_cache = {"default": model}
    available_model_paths = discover_model_paths(
        default_model_path=model_path,
        models_config_path=BASE_DIR / "src" / "models" / "models_config.json",
    )
    model_versions = {name: "unknown" for name in available_model_paths.keys()}

    models_config_path = BASE_DIR / "src" / "models" / "models_config.json"
    if models_config_path.exists():
        try:
            with open(models_config_path, "r", encoding="utf-8") as file_obj:
                config = json.load(file_obj)
            for name, info in config.get("models", {}).items():
                if name in model_versions:
                    model_versions[name] = str(info.get("version", "unknown"))
        except Exception:
            logger.warning("Failed to load model versions from %s", models_config_path)
    logger.info("Model loaded from %s", model_path)

    yield

    model_cache.clear()
    logger.info("Resources cleaned up")


app = FastAPI(
    title="PCB Defect Detection API",
    description="Автоматическое обнаружение дефектов печатных плат",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
environment = os.getenv("ENVIRONMENT", "development").strip().lower()
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [
    origin.strip() for origin in raw_allowed_origins.split(",") if origin.strip()
]

if environment == "production" and "*" in allowed_origins:
    raise RuntimeError("ALLOWED_ORIGINS cannot contain '*' in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
rate_limit_window_seconds = 60
rate_limit_hits = defaultdict(deque)
rate_limit_lock = Lock()


@app.middleware("http")
async def ip_rate_limit_middleware(request: Request, call_next):
    path = request.url.path

    if (
        path.startswith("/css/")
        or path.startswith("/js/")
        or path.startswith("/results/")
        or path.startswith("/uploads/")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path.startswith("/openapi.json")
        or path.startswith("/health")
    ):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    with rate_limit_lock:
        timestamps = rate_limit_hits[client_ip]
        while timestamps and now - timestamps[0] > rate_limit_window_seconds:
            timestamps.popleft()

        if len(timestamps) >= rate_limit_per_minute:
            retry_after = max(1, int(rate_limit_window_seconds - (now - timestamps[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Max {rate_limit_per_minute} requests per minute per IP"
                },
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)

    return await call_next(request)


# Статические файлы (frontend)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

app.include_router(auth_router)
app.include_router(websocket_router)
app.include_router(batch_router)
app.include_router(model_router)
app.include_router(export_router)
app.include_router(history_router)
app.include_router(detect_router)
app.include_router(file_router)
app.include_router(analytics_router)

# Глобальная переменная для модели
model = None
model_cache = {}
available_model_paths = {}
model_versions = {}

# Storage directories from env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / os.getenv("STORAGE_DIR", "storage")
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "storage/uploads")
RESULTS_DIR = BASE_DIR / os.getenv("RESULTS_DIR", "storage/results")

UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)


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
        "model_loaded": model is not None,
    }


@app.get("/health")
async def health_check(current_user: User = Depends(get_current_user)):
    """Проверка работоспособности"""
    return {"status": "healthy", "model_status": "loaded" if model else "not_loaded"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.api.main:app", host=host, port=port, reload=True)
