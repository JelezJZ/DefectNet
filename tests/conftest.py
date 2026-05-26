import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def get_test_model_path():
    root = Path(__file__).resolve().parent.parent
    model_dir = root / "models" / "trained"
    models = list(model_dir.glob("*.pt"))
    if not models:
        raise RuntimeError(f"Models not found in {model_dir}")
    return str(models[0])


@pytest.fixture(scope="session")
def client():
    os.environ["DATABASE_URL"] = "sqlite:///./pcb_defects_test.db"
    os.environ["MODEL_PATH"] = get_test_model_path()

    from src.api.main import app

    with TestClient(app) as test_client:
        yield test_client

    if os.path.exists("pcb_defects_test.db"):
        os.remove("pcb_defects_test.db")


@pytest.fixture
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
