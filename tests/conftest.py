import os
import time
import uuid
from contextlib import ExitStack
from pathlib import Path

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./pcb_defects_test.db"

from fastapi.testclient import TestClient

from src.api.main import app

BASE_DIR = Path(__file__).resolve().parent.parent
TEST_IMAGE_PATH = BASE_DIR / "datasets" / "test_image.jpg"

TERMINAL_STATES = {"SUCCESS", "FAILURE"}
STATUS_TIMEOUT = float(os.getenv("TEST_STATUS_TIMEOUT", "120"))
STATUS_POLL_INTERVAL = float(os.getenv("TEST_STATUS_POLL_INTERVAL", "0.25"))

WORKER_HINT = (
    "Celery worker is required for detection tests.\n"
    "Start it with:\n"
    "  celery -A src.tasks.celery_config.celery_app worker --loglevel=INFO --pool=solo\n"
    "and make sure the broker is up (redis/CELERY_BROKER_URL)."
)

def assert_worker_available() -> None:
    """Fails fast with a readable message instead of polling a dead queue."""
    from src.tasks.celery_config import celery_app

    try:
        replies = celery_app.control.ping(timeout=2.0)
    except Exception as err:
        pytest.fail(f"{WORKER_HINT}\nBroker unreachable: {err}")

    if not replies:
        pytest.fail(WORKER_HINT)

def get_test_model_path():
    root = Path(__file__).resolve().parent.parent
    model_dir = root / "models" / "trained"
    models = sorted(model_dir.glob("*.pt"))
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
def wait_for_batch(client, auth_headers):
    """Polls /detect/status/{batch_id} until the Celery job reaches a terminal state.

    Detection is asynchronous: a single status request right after the upload always
    returns PENDING (that covers both "still queued" and "unknown task id")."""

    def _wait(batch_id, timeout=STATUS_TIMEOUT, interval=STATUS_POLL_INTERVAL):
        deadline = time.monotonic() + timeout
        payload = {}

        while time.monotonic() < deadline:
            response = client.get(f"/detect/status/{batch_id}", headers=auth_headers)
            assert response.status_code == 200, response.text

            payload = response.json()
            if payload.get("state") in TERMINAL_STATES:
                return payload

            time.sleep(interval)

        raise AssertionError(
            f"Batch {batch_id} is still {payload.get('state')!r} after {timeout}s"
        )

    return _wait


@pytest.fixture(scope="session")
def run_single_detect(client, auth_headers, wait_for_batch):
    """Runs /detect/single-detect and returns the aggregated result of the finished job."""

    def _run(params=None, image_path=TEST_IMAGE_PATH, filename="image.jpg"):
        assert_worker_available()

        query = {"model_name": "default"}
        query.update(params or {})

        with open(image_path, "rb") as f:
            files = {"file": (filename, f, "image/jpeg")}
            response = client.post(
                "/detect/single-detect",
                params=query,
                files=files,
                headers=auth_headers,
            )

        assert response.status_code == 200, response.text

        status = wait_for_batch(response.json()["detection_id"])
        assert status["state"] == "SUCCESS", status

        return status["result"]

    return _run


@pytest.fixture(scope="session")
def run_batch_detect(client, auth_headers, wait_for_batch):
    """Uploads files to /detect/batch-detect and returns (enqueued payload, result)."""

    def _run(files_spec, params=None):
        assert_worker_available()

        query = {"model_name": "default"}
        query.update(params or {})

        with ExitStack() as stack:
            files = [
                (
                    "files",
                    (filename, stack.enter_context(open(path, "rb")), "image/jpeg"),
                )
                for filename, path in files_spec
            ]

            response = client.post(
                "/detect/batch-detect",
                params=query,
                files=files,
                headers=auth_headers,
            )

        assert response.status_code == 202, response.text

        enqueued = response.json()
        status = wait_for_batch(enqueued["batch_id"])
        assert status["state"] == "SUCCESS", status

        return enqueued, status["result"]

    return _run


@pytest.fixture(scope="session")
def created_inspection(run_single_detect):
    result = run_single_detect()
    assert result["successful"] == 1, result

    detection = result["results"][0]
    assert detection["result_image_url"], (
        f"result_image is missing, the test image produced no defects: {detection}"
    )

    return {
        "inspection_id": detection["inspection_id"],
        "result_image": detection["result_image_url"],
        "detection": detection,
    }

@pytest.fixture(autouse=True)
def reset_rate_limit_and_cache():
    # NOTE: the detection cache lives in the Celery worker process, so clearing it
    # here only affects an in-process (eager) run of the tasks.
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