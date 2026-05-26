import io


def test_detect_rejects_non_image(client, auth_headers):
    files = {"file": ("bad.txt", io.BytesIO(b"not image"), "text/plain")}
    response = client.post(
        "/detect?model_name=default",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_detect_invalid_params(client, auth_headers):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128
    files = {"file": ("x.png", io.BytesIO(png), "image/png")}
    response = client.post(
        "/detect?confidence=2&iou=0.5&imgsz=1024&model_name=default",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 422

def test_detect_valid_params(client, auth_headers):
    with open("./datasets/test_image.jpg", "rb") as f:
        files = {"file": ("image.jpg", f, "image/jpeg")}
        response = client.post(
            "/detect?confidence=0.5&iou=0.5&imgsz=1024&model_name=default&save_image=true",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 200

def test_batch_detect(client, auth_headers):
    with open("./datasets/test_image.jpg", "rb") as f1, \
        open("./datasets/test_image_2.jpg", "rb") as f2, \
        open("./datasets/test_image_3.jpg", "rb") as f3:
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