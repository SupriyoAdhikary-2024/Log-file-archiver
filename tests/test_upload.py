"""Integration tests for Flask API endpoints and uploads."""

import io
import pytest
from app import create_app


@pytest.fixture
def client(tmp_path):
    test_db = tmp_path / "test_archiver.db"
    app = create_app({"TESTING": True, "DB_PATH": str(test_db)})
    with app.test_client() as client:
        yield client


def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Log File Error Archiver" in response.data


def test_upload_sample_log(client):
    sample_content = (
        "2026-11-10 10:00:00 INFO Server started\n"
        "2026-11-10 10:01:00 ERROR Database connection failed\n"
        "2026-11-10 10:02:00 WARNING High CPU usage\n"
        "2026-11-10 10:03:00 CRITICAL Server crashed\n"
        "2026-11-10 10:04:00 INFO Server restarted\n"
        "2026-11-10 10:05:00 ERROR Login failed\n"
    )

    data = {
        "file": (io.BytesIO(sample_content.encode("utf-8")), "sample.log")
    }
    response = client.post("/api/uploads", data=data, content_type="multipart/form-data")
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data["upload_id"] == 1
    assert json_data["total_lines"] == 6
    assert json_data["archived_count"] == 4
    assert json_data["ignored_count"] == 2

    # Stats check
    stats_resp = client.get("/api/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.get_json()
    assert stats["total_errors"] == 4
    assert stats["total_uploads"] == 1
    assert stats["by_severity"] == {"WARNING": 1, "ERROR": 2, "CRITICAL": 1}

    # Query errors
    errors_resp = client.get("/api/errors")
    assert errors_resp.status_code == 200
    errors_data = errors_resp.get_json()
    assert errors_data["total_records"] == 4
    assert len(errors_data["records"]) == 4


def test_duplicate_upload_rejection(client):
    content = "2026-11-10 10:01:00 ERROR Database connection failed\n"
    data = {"file": (io.BytesIO(content.encode("utf-8")), "test.log")}

    # First upload
    res1 = client.post("/api/uploads", data=data, content_type="multipart/form-data")
    assert res1.status_code == 201

    # Second upload with same content
    data2 = {"file": (io.BytesIO(content.encode("utf-8")), "test_again.log")}
    res2 = client.post("/api/uploads", data=data2, content_type="multipart/form-data")
    assert res2.status_code == 409
    assert "already been uploaded" in res2.get_json()["error"]


def test_invalid_extension(client):
    data = {"file": (io.BytesIO(b"some content"), "exploit.exe")}
    res = client.post("/api/uploads", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "Invalid file extension" in res.get_json()["error"]


def test_empty_file_upload(client):
    data = {"file": (io.BytesIO(b""), "empty.log")}
    res = client.post("/api/uploads", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "empty" in res.get_json()["error"]


def test_invalid_utf8(client):
    data = {"file": (io.BytesIO(b"\xff\xfe\x00\x00"), "corrupt.log")}
    res = client.post("/api/uploads", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "valid UTF-8" in res.get_json()["error"]


def test_oversized_file(client):
    large_bytes = b"A" * (2 * 1024 * 1024 + 10)
    data = {"file": (io.BytesIO(large_bytes), "oversized.log")}
    res = client.post("/api/uploads", data=data, content_type="multipart/form-data")
    assert res.status_code == 413


def test_filtering_and_search(client):
    sample = (
        "2026-11-10 10:01:00 ERROR Database connection failed\n"
        "2026-11-10 10:02:00 WARNING High CPU usage\n"
        "2026-11-10 10:03:00 CRITICAL Server crashed\n"
    )
    client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(sample.encode("utf-8")), "data.log")},
        content_type="multipart/form-data",
    )

    # Filter by severity
    res_crit = client.get("/api/errors?severity=CRITICAL")
    assert res_crit.status_code == 200
    data_crit = res_crit.get_json()
    assert data_crit["total_records"] == 1
    assert data_crit["records"][0]["severity"] == "CRITICAL"

    # Search keyword
    res_search = client.get("/api/errors?q=CPU")
    assert res_search.status_code == 200
    data_search = res_search.get_json()
    assert data_search["total_records"] == 1
    assert data_search["records"][0]["message"] == "High CPU usage"


def test_csv_export_and_formula_injection(client):
    sample = (
        "2026-11-10 10:01:00 ERROR =1+1 Dangerous formula in log\n"
        "2026-11-10 10:02:00 WARNING Normal message\n"
    )
    client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(sample.encode("utf-8")), "formula.log")},
        content_type="multipart/form-data",
    )

    export_res = client.get("/api/export")
    assert export_res.status_code == 200
    assert export_res.headers["Content-Type"].startswith("text/csv")
    csv_text = export_res.data.decode("utf-8")

    # Formula prefix '=' must be prepended with a quote to prevent CSV injection
    assert "'=1+1 Dangerous formula in log" in csv_text
    assert "Normal message" in csv_text
