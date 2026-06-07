import pytest
from importlib import reload
import src.api.main as main

def test_rate_limit(client, auth_headers):
    status_codes = []
    for _ in range(101):
        r = client.get("/history", headers=auth_headers)
        status_codes.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in status_codes

def test_cors_production_guard_fails(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")

    with pytest.raises(RuntimeError) as excinfo:
        reload(main)
    
    assert "ALLOWED_ORIGINS cannot contain '*'" in str(excinfo.value)