import re

def test_image_paths_format(created_inspection):
    inspection_id = created_inspection["inspection_id"]

    path_pattern = rf"^/(results|uploads)/\d{{4}}/\d{{2}}/\d{{2}}/{inspection_id}/.+"

    res_path = created_inspection["result_image"]
    upl_path = res_path.replace("/results/", "/uploads/").replace("/result_", "/upload_")

    assert re.match(path_pattern, res_path), f"Result path format mismatch: {res_path}"
    assert re.match(path_pattern, upl_path), f"Upload path format mismatch: {upl_path}"

def test_result_image_accessibility(client, auth_headers, created_inspection):
    path = created_inspection["result_image"]
    
    response = client.get(path, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

def test_upload_image_accessibility(client, auth_headers, created_inspection):
    result_path = created_inspection["result_image"]
    upload_path = result_path.replace("/results/", "/uploads/").replace("/result_", "/upload_")
    
    response = client.get(upload_path, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"