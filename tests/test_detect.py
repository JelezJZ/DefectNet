import io
import os
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
TEST_IMAGE_PATH = BASE_DIR / "datasets" / "test_image.jpg"
TEST_IMAGE_PATH_2 = BASE_DIR / "datasets" / "test_image_2.jpg"
TEST_IMAGE_PATH_3 = BASE_DIR / "datasets" / "test_image_3.jpg"

def test_detect_rejects_non_image(client, auth_headers):
    files = {"file": ("bad.txt", io.BytesIO(b"not image"), "text/plain")}
    response = client.post(
        "/detect/single-detect?model_name=default",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_magic_bytes_mismatch(client, auth_headers):
    png = b"This is definitely not a PNG file"
    files = {"file": ("x.png", io.BytesIO(png), "image/png")}
    response = client.post(
        "/detect/single-detect",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 400

@pytest.mark.parametrize("invalid_params", [
    {"confidence": 2.0},
    {"confidence": -0.1},
    {"imgsz": 99999},
    {"imgsz": 128},
    {"iou": 1.1},
    {"iou": -0.1},
])
def test_detect_invalid_params(client, auth_headers, invalid_params):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128
    files = {"file": ("x.png", io.BytesIO(png), "image/png")}
    response = client.post(
        "/detect/single-detect",
        params=invalid_params,
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 422

def test_too_large_image(client, auth_headers):
    size = 11 * 1024 * 1024
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * size
    files = {"file": ("x.png", io.BytesIO(png), "image/png")}
    response = client.post(
        "/detect/single-detect",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 413

def test_detect_valid_params(run_single_detect):
    result = run_single_detect(
        params={"confidence": 0.5, "iou": 0.5, "imgsz": 1024, "save_image": "true"}
    )

    assert result["status"] == "completed", result
    assert result["total_images"] == 1, result
    assert result["successful"] == 1, result
    assert result["failed"] == 0, result

    assert "results" in result, f"Ключ 'results' отсутствует в ответе: {result}"
    detection = result["results"][0]

    assert detection["status"] == "success", detection
    assert detection["inspection_id"], detection
    assert detection["result_image_url"].startswith("/results/"), detection

def test_unknown_model_name(client, auth_headers):
    with open(TEST_IMAGE_PATH, "rb") as f:
        files = {"file": ("image.jpg", f, "image/jpeg")}
        response = client.post(
            "/detect/single-detect?model_name=unknown_model_name",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "unknown_model_name" in response.json()["detail"]

def test_batch_detect(run_batch_detect):
    enqueued, result = run_batch_detect(
        [
            ("image_1.jpg", TEST_IMAGE_PATH),
            ("image_2.jpg", TEST_IMAGE_PATH_2),
            ("image_3.jpg", TEST_IMAGE_PATH_3),
        ]
    )

    assert enqueued["status"] == "queued", enqueued
    assert enqueued["total_images"] == 3, enqueued
    assert enqueued["batch_id"], enqueued

    assert "results" in result, f"Ключ 'results' отсутствует в ответе: {result}"

    assert result["total_images"] == 3, result
    assert result["successful"] == 3, result
    assert result["failed"] == 0, result

    assert isinstance(result["results"], list)
    assert len(result["results"]) == 3

    for detection in result["results"]:
        assert detection["status"] == "success", detection
        assert detection["inspection_id"], detection

def test_batch_detect_rejects_bad_file(client, auth_headers):
    with open(TEST_IMAGE_PATH, "rb") as f1, \
        open(TEST_IMAGE_PATH_2, "rb") as f2:
        files = [
            ("files", ("image_1.jpg", f1, "image/jpeg")),
            ("files", ("image_2.jpg", f2, "image/jpeg")),
            ("files", ("image_3.jpg",  io.BytesIO(b"bad_file"), "image/jpeg"))
        ]
        response = client.post(
            "/detect/batch-detect",
            files=files,
            headers=auth_headers,
        )

    assert response.status_code == 400
    assert response.json()["detail"]

def test_exceeded_max_batch_detect(client, auth_headers):
    max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "20"))

    with open(TEST_IMAGE_PATH, "rb") as f:
        image_content = f.read()
    
    files = []
    for i in range(1, max_batch_size + 2):
        files.append(
            ("files", (f"image_{i}.jpg", io.BytesIO(image_content), "image/jpeg"))
        )
    response = client.post(
        "/detect/batch-detect",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == f"Maximum {max_batch_size} images allowed per batch"