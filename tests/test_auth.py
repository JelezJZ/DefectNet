import uuid
import pytest

@pytest.fixture
def user_data():
    unique_suffix = uuid.uuid4().hex[:8]
    return {
        "username": f"test_user_{unique_suffix}",
        "email": f"test_{unique_suffix}@example.com",
        "password": "StrongPass123",
        "full_name": "Test User"
    }

def test_register_and_login_flow(client, user_data):
    r = client.post("/auth/register", json=user_data)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data

    r2 = client.post("/auth/login", json={
        "username": user_data["username"],
        "password": user_data["password"]
    })
    assert r2.status_code == 200
    assert "access_token" in r2.json()

def test_register_duplicate_user(client, user_data):
    client.post("/auth/register", json=user_data)
    r = client.post("/auth/register", json=user_data)
    assert r.status_code == 400

def test_login_wrong_password(client, user_data):
    client.post("/auth/register", json=user_data)
    r = client.post("/auth/login", json={
        "username": user_data["username"],
        "password": "wrong_password"
    })
    assert r.status_code == 401

@pytest.mark.parametrize("endpoint, method", [
    ("/auth/me", "get"),
    ("/models/list", "get"),
    ("/models/compare", "post"),
    ("/models/available", "get"),
    ("/export/pdf/123", "get"),
    ("/export/json/123", "get"),
    ("/export/image/123", "get"),
    ("/export/csv", "get"),
    ("/history", "get"),
    ("/history/123", "get"),
    ("/detect/single-detect", "post"),
    ("/detect/batch-detect", "post"),
    ("/detect/status/123", "get"),
    ("/results/123", "get"),
    ("/uploads/123", "get"),
    ("/analytics/dashboard", "get"),
    ("/health", "get"),
])
def test_unauthorized_access(client, endpoint, method):
    http_method = getattr(client, method)
    response = http_method(endpoint)
    
    assert response.status_code == 401