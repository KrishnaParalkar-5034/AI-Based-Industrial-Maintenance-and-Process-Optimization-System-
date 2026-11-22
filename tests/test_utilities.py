"""
Unit and integration tests for Tab 5: Utilities & System Operations.
Covers CSV batch analysis, sample CSV download, audit logs, audit CSV export,
system health info, model hot-reloading, and telemetry adapter switching.
"""
import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_download_sample_csv_endpoint():
    """Verify GET /api/v1/analyze/sample-csv returns valid downloadable CSV content."""
    res = client.get("/api/v1/analyze/sample-csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert "Content-Disposition" in res.headers
    content = res.text
    lines = content.strip().split("\n")
    assert len(lines) >= 10, "Expected at least 10 lines in sample CSV"
    headers = lines[0].split(",")
    assert len(headers) >= 50, f"Expected at least 50 sensor headers, got {len(headers)}"


def test_analyze_csv_batch_endpoint():
    """Verify POST /api/v1/analyze/csv correctly parses and scores batch telemetry."""
    # First fetch sample CSV
    sample_res = client.get("/api/v1/analyze/sample-csv")
    assert sample_res.status_code == 200
    csv_bytes = sample_res.content

    # Upload to analyze
    files = {"file": ("test_batch.csv", io.BytesIO(csv_bytes), "text/csv")}
    res = client.post("/api/v1/analyze/csv", files=files)
    assert res.status_code == 200
    data = res.json()

    required_keys = [
        "total_rows", "peak_risk", "mean_risk", "overall_regime",
        "alarms_triggered", "top_diagnosed_fault_id", "top_diagnosed_fault_name",
        "top_fault_confidence", "primary_contributing_unit", "time_series", "summary_markdown"
    ]
    for k in required_keys:
        assert k in data, f"Missing key {k} in CSVAnalysisResponse"

    assert data["total_rows"] > 0
    assert 0.0 <= data["peak_risk"] <= 1.0
    assert 0.0 <= data["mean_risk"] <= 1.0
    assert data["overall_regime"] in ["NORMAL", "WARNING", "CRITICAL"]
    assert len(data["time_series"]) > 0
    assert "sample" in data["time_series"][0]
    assert "risk_score" in data["time_series"][0]


def test_audit_logs_query_and_export():
    """Verify GET /api/v1/audit-logs and GET /api/v1/audit-logs/export."""
    # Trigger an action to create an audit record
    client.post("/api/v1/stream/control", json={"action": "speed", "speed": 1.5, "operator_user": "AuditTestUser"})

    # Query logs
    res = client.get("/api/v1/audit-logs?limit=10&user=AuditTestUser")
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert logs[0]["user"] == "AuditTestUser"

    # Export CSV
    exp_res = client.get("/api/v1/audit-logs/export")
    assert exp_res.status_code == 200
    assert "text/csv" in exp_res.headers.get("content-type", "")
    assert "ID,Timestamp" in exp_res.text or "ID" in exp_res.text


def test_system_info_endpoint():
    """Verify GET /api/v1/system/info returns valid metadata."""
    res = client.get("/api/v1/system/info")
    assert res.status_code == 200
    data = res.json()

    assert "model_artifacts" in data
    assert "bundle" in data["model_artifacts"]
    assert data["model_artifacts"]["bundle"]["exists"] is True

    assert "database" in data
    assert "engine" in data["database"]
    assert "status" in data["database"]

    assert "runtime" in data
    assert "python_version" in data["runtime"]
    assert "active_adapter" in data["runtime"]


def test_model_hot_reload_endpoint():
    """Verify POST /api/v1/models/reload reloads artifacts and replay_sample without error."""
    res = client.post("/api/v1/models/reload")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "success"
    assert data.get("models_loaded") is True
    assert "dataset_origin" in data
    assert data["dataset_origin"] in ["real_tep_kaggle_dat", "real_tep_csv", "synthetic_ar1"]
    assert "available_runs_count" in data
    assert data["available_runs_count"] > 0
    assert "current_run_id" in data


def test_switch_adapter_control_action():
    """Verify stream control action 'switch_adapter'."""
    # Switch to simulator
    res = client.post("/api/v1/stream/control", json={
        "action": "switch_adapter",
        "adapter_type": "simulator"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Verify stream status reflects new simulator adapter
    stat = client.get("/api/v1/stream/status").json()
    assert stat["current_run_id"] == "LIVE_STREAM"

    # Switch back to replay
    res2 = client.post("/api/v1/stream/control", json={
        "action": "switch_adapter",
        "adapter_type": "replay"
    })
    assert res2.status_code == 200
    stat2 = client.get("/api/v1/stream/status").json()
    assert stat2["current_run_id"] != "LIVE_STREAM" or len(stat2["available_runs"]) > 0


def test_reset_demo_database_endpoint():
    """Verify POST /api/v1/system/reset-db resets historian and logs clean reset."""
    res = client.post("/api/v1/system/reset-db")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"

    # Verify audit logs only contain the reset log
    logs_res = client.get("/api/v1/audit-logs")
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) == 1
    assert logs[0]["action"] == "SYSTEM_RESET_DB"
