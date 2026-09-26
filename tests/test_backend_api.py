import io
import pytest
from fastapi.testclient import TestClient

import backend.api as api_module
import backend.database as database_module


@pytest.fixture(autouse=True)
def isolated_backend(tmp_path, monkeypatch):
    db_path = tmp_path / "hr_data_test.db"
    monkeypatch.setattr(api_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(database_module, "DB_PATH", str(db_path))
    database_module.init_db()
    yield


def _client():
    return TestClient(api_module.app)


def _salary_bytes():
    csv_text = (
        "员工编号,姓名,部门,基本工资,绩效评分\n"
        "E001,张三,技术部,20000,90\n"
        "E002,李四,技术部,22000,85\n"
        "E003,王五,销售部,18000,88\n"
    )
    return io.BytesIO(csv_text.encode("utf-8-sig"))


def test_health_returns_ok():
    with _client() as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data


def test_analyze_salary_csv():
    with _client() as client:
        response = client.post(
            "/api/analyze_salary",
            files={"file": ("salary.csv", _salary_bytes(), "text/csv")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == 3
    assert data["group_col"] == "部门"
    assert data["value_col"] == "基本工资"
    assert len(data["group_stats"]) == 2
    assert data["history_id"] is not None


def test_history_returns_records():
    with _client() as client:
        client.post(
            "/api/analyze_salary",
            files={"file": ("salary.csv", _salary_bytes(), "text/csv")},
        )
        response = client.get("/api/history?limit=10")
    assert response.status_code == 200
    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= 1
    assert records[0]["page_type"] == "salary"


def test_empty_file_returns_400():
    with _client() as client:
        response = client.post(
            "/api/analyze_salary",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
    assert response.status_code == 400


def test_wrong_format_returns_400():
    with _client() as client:
        response = client.post(
            "/api/analyze_salary",
            files={"file": ("bad.xlsx", io.BytesIO(b"not an excel file"), "application/octet-stream")},
        )
    assert response.status_code == 400


def test_too_large_file_returns_413(monkeypatch):
    monkeypatch.setattr(api_module, "MAX_BYTES", 100)
    with _client() as client:
        response = client.post(
            "/api/analyze_salary",
            files={"file": ("large.csv", io.BytesIO(b"x" * 200), "text/csv")},
        )
    assert response.status_code == 413