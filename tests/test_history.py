def test_inspection_full_details_in_history(client, auth_headers, created_inspection):
    r = client.get(f"/history/{created_inspection["inspection_id"]}", headers=auth_headers)
    assert r.status_code == 200

    data = r.json()

    expected_details = {
        "filename", "image_width", "image_height", 
        "confidence_threshold", "total_defects", "status", 
        "severity_breakdown", "detections", "result_image_path", 
        "original_image_path", "processing_time", "operator_id"
    }

    missing_keys = expected_details - set(data.keys())
    assert not missing_keys, f"В ответе отсутствуют ключи: {missing_keys}"

def test_non_existent_inspection_id_in_history(client, auth_headers):
    r = client.get(f"/history/non_existent_inspection_id", headers=auth_headers)
    assert r.status_code == 404