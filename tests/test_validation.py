import io


MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA"
    b"\xdd\x8d\xb1\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_detect_rejects_imgsz_not_multiple_of_32(client, auth_headers):
    files = {"file": ("x.png", io.BytesIO(MINIMAL_PNG), "image/png")}
    response = client.post(
        "/detect/single-detect?confidence=0.25&iou=0.45&imgsz=1000&model_name=default",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_detect_rejects_iou_out_of_range(client, auth_headers):
    files = {"file": ("x.png", io.BytesIO(MINIMAL_PNG), "image/png")}
    response = client.post(
        "/detect/single-detect?confidence=0.25&iou=1.5&imgsz=1024&model_name=default",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_detect_rejects_mime_mismatch(client, auth_headers):
    files = {"file": ("x.jpg", io.BytesIO(MINIMAL_PNG), "image/jpeg")}
    response = client.post(
        "/detect/single-detect?confidence=0.25&iou=0.45&imgsz=1024&model_name=default",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 400
