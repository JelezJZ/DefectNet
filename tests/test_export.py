def test_export_json_not_found(client, auth_headers):
    response = client.get(
        "/export/json/non-existent-id",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_export_image_rejects_invalid_format(client, auth_headers):
    response = client.get(
        "/export/image/non-existent-id?format=bmp",
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_export_csv_returns_file(client, auth_headers):
    response = client.get(
        "/export/csv",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
