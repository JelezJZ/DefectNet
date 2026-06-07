import os
import uuid
from pathlib import Path
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./pcb_defects_test.db"

from fastapi.testclient import TestClient
from src.api.main import app

BASE_DIR = Path(__file__).resolve().parent.parent
TEST_IMAGE_PATH = BASE_DIR / "datasets" / "test_image.jpg"

def get_test_model_path():
    root = Path(__file__).resolve().parent.parent
    model_dir = root / "models" / "trained"
    models = list(model_dir.glob("*.pt"))
    if not models:
        raise RuntimeError(f"Models not found in {model_dir}")
    return str(models[0])


@pytest.fixture(scope="session")
def client():
    os.environ["MODEL_PATH"] = get_test_model_path()

    with TestClient(app) as test_client:
        yield test_client

    if os.path.exists("pcb_defects_test.db"):
        os.remove("pcb_defects_test.db")


@pytest.fixture(scope="session")
def auth_headers(client):
    user_id = uuid.uuid4().hex[:8]
    payload = {
        "username": f"user_{user_id}",
        "email": f"test_{user_id}@example.com",
        "password": "StrongPass123",
        "full_name": "Test User"
    }
    
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 200 
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="session")
def created_inspection(client, auth_headers):
    payload = {"model_name": "default"}
    with open(TEST_IMAGE_PATH, "rb") as f:
        files = {"file": ("image.jpg", f, "image/jpeg")}
        r = client.post("/detect", params=payload, files=files, headers=auth_headers)
    
    assert r.status_code == 200
    data = r.json()
    return data

@pytest.fixture(autouse=True)
def reset_rate_limit_and_cache():
    from src.api.main import rate_limit_hits, rate_limit_lock
    with rate_limit_lock:
        rate_limit_hits.clear()
    
    try:
        from src.services.detection_cache import _CACHE, _LOCK
        with _LOCK:
            _CACHE.clear()
    except ImportError:
        pass
        
    yield