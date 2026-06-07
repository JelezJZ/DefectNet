import io
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
TEST_IMAGE_PATH = BASE_DIR / "datasets" / "test_image.jpg"
TEST_IMAGE_PATH_2 = BASE_DIR / "datasets" / "test_image_2.jpg"
TEST_IMAGE_PATH_3 = BASE_DIR / "datasets" / "test_image_3.jpg"

def test_detect_rejects_non_image(client, auth_headers):
    files = {"file": ("bad.txt", io.BytesIO(b"not image"), "text/plain")}
    response = client.post(
        "/detect?model_name=default",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_magic_bytes_mismatch(client, auth_headers):
    png = b"This is definitely not a PNG file"
    files = {"file": ("x.png", io.BytesIO(png), "image/png")}
    response = client.post(
        "/detect",
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
        "/detect",
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
        "/detect",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 413

def test_detect_valid_params(client, auth_headers):
    with open(TEST_IMAGE_PATH, "rb") as f:
        files = {"file": ("image.jpg", f, "image/jpeg")}
        response = client.post(
            "/detect?confidence=0.5&iou=0.5&imgsz=1024&model_name=default&save_image=true",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        
        assert "results" in data, f"Ключ 'results' отсутствует в ответе: {data}"
        assert "inspection_id" in data
        assert data.get("success") is True

def test_unknown_model_name(client, auth_headers):
    with open(TEST_IMAGE_PATH, "rb") as f:
        files = {"file": ("image.jpg", f, "image/jpeg")}
        response = client.post(
            "/detect?model_name=unknown_model_name",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 400

def test_batch_detect(client, auth_headers):
    with open(TEST_IMAGE_PATH, "rb") as f1, \
        open(TEST_IMAGE_PATH_2, "rb") as f2, \
        open(TEST_IMAGE_PATH_3, "rb") as f3:
        files = [
            ("files", ("image_1.jpg", f1, "image/jpeg")),
            ("files", ("image_2.jpg", f2, "image/jpeg")),
            ("files", ("image_3.jpg", f3, "image/jpeg"))
        ]
        response = client.post(
            "/batch-detect",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()

        assert "results" in data, f"Ключ 'results' отсутствует в ответе: {data}"
        
        assert data["total_images"] == 3
        assert data["processed"] == 3

        assert isinstance(data["results"], list)
        assert len(data["results"]) == 3

        assert "batch_id" in data
        assert len(data["batch_id"]) > 0

def test_one_bad_file_batch_detect(client, auth_headers):
    with open(TEST_IMAGE_PATH, "rb") as f1, \
        open(TEST_IMAGE_PATH_2, "rb") as f2:
        files = [
            ("files", ("image_1.jpg", f1, "image/jpeg")),
            ("files", ("image_2.jpg", f2, "image/jpeg")),
            ("files", ("image_3.jpg",  io.BytesIO(b"bad_file"), "image/jpeg"))
        ]
        response = client.post(
            "/batch-detect",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()

        res_map = {r["filename"]: r for r in data["results"]}
    
        assert res_map["image_1.jpg"]["status"] == "success"
        assert res_map["image_2.jpg"]["status"] == "success"
        assert res_map["image_3.jpg"]["status"] == "error"
        
        assert "error" in res_map["image_3.jpg"]

def test_exceeded_max_batch_detect(client, auth_headers):
    with open(TEST_IMAGE_PATH, "rb") as f:
        image_content = f.read()
    
    files = []
    for i in range(1, 22):
        files.append(
            ("files", (f"image_{i}.jpg", io.BytesIO(image_content), "image/jpeg"))
        )
    response = client.post(
        "/batch-detect",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == f"Maximum 20 images per batch"