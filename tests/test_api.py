"""
Integration & End-to-End API Tests for TEP Predictive Maintenance Backend.
Tests REST endpoints, TreeSHAP explainability, alarm persistence, and WebSocket telemetry stream.
"""
import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db import Alarm, SessionLocal

client = TestClient(app)


def test_health_check_endpoint():
    """Verify /health reports database connection, models loaded, and advisory mode."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["database_connected"] is True
    assert data["models_loaded"] is True
    assert data["advisory_mode"] is True
    assert "current_run" in data


def test_prometheus_metrics_endpoint():
    """Verify /metrics exposes Prometheus formatted metrics."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "tep_active_ws_clients" in res.text
    assert "tep_active_alarms_total" in res.text
    assert "tep_playback_speed" in res.text
    assert "tep_inference_latency_ms" in res.text


def test_stream_status_and_control():
    """Verify stream status retrieval and control actions (play, pause, seek, speed)."""
    # 1. Get status
    s_res = client.get("/api/v1/stream/status")
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert "current_run_id" in s_data
    assert "available_runs" in s_data
    assert len(s_data["available_runs"]) > 0

    # 2. Control: Pause
    p_res = client.post("/api/v1/stream/control", json={"action": "pause"})
    assert p_res.status_code == 200

    # 3. Control: Speed
    spd_res = client.post("/api/v1/stream/control", json={"action": "speed", "speed": 2.5})
    assert spd_res.status_code == 200

    # 4. Control: Seek
    sk_res = client.post("/api/v1/stream/control", json={"action": "seek", "step": 15})
    assert sk_res.status_code == 200

    # 5. Verify updated status
    updated_res = client.get("/api/v1/stream/status")
    assert updated_res.json()["current_step"] == 15
    assert updated_res.json()["speed"] == 2.5
    assert updated_res.json()["is_playing"] is False


def test_explainability_endpoint():
    """Verify exact TreeSHAP feature attributions and P&ID unit breakdown."""
    # Fetch status to get current run
    s_res = client.get("/api/v1/stream/status")
    run_id = s_res.json()["current_run_id"]

    res = client.get(f"/api/v1/explain/{run_id}/10")
    assert res.status_code == 200
    data = res.json()
    assert "top_drivers" in data
    assert len(data["top_drivers"]) > 0
    assert "unit_attributions_pct" in data
    # Ensure all 6 P&ID units exist in attribution map
    assert "Reactor" in data["unit_attributions_pct"]
    assert "Product Stripper" in data["unit_attributions_pct"]
    assert "prescriptive_actions" in data
    assert "action_steps" in data["prescriptive_actions"]


def test_alarm_management_and_audit():
    """Test creating an alarm, querying it, acknowledging it, and auditing the update."""
    # Insert a test alarm directly into DB
    with SessionLocal() as db:
        test_alarm = Alarm(
            run_id="TEST_RUN_99",
            step=42,
            severity="CRITICAL",
            fault_diagnosis="Fault 4: Reactor cooling water inlet temp step",
            top_unit="Reactor",
            top_shap_drivers_json=json.dumps([{"feature": "Reactor Temp", "val": 0.45}]),
            status="ACTIVE"
        )
        db.add(test_alarm)
        db.commit()
        alarm_id = test_alarm.id

    # 1. Query alarms
    get_res = client.get(f"/api/v1/alarms?status=ACTIVE")
    assert get_res.status_code == 200
    alarms = get_res.json()
    matching = [a for a in alarms if a["id"] == alarm_id]
    assert len(matching) == 1
    assert matching[0]["severity"] == "CRITICAL"

    # 2. Acknowledge alarm
    patch_res = client.patch(
        f"/api/v1/alarms/{alarm_id}",
        json={
            "status": "ACKNOWLEDGED",
            "acknowledged_by": "SeniorOperator-Jane",
            "operator_note": "Field technician dispatched to reactor cooling jacket."
        }
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["status"] == "ACKNOWLEDGED"
    assert updated["acknowledged_by"] == "SeniorOperator-Jane"


def test_models_benchmark_and_shift_handover():
    """Verify model benchmarks and shift handover report generation."""
    # Benchmarks
    b_res = client.get("/api/v1/models/benchmarks")
    assert b_res.status_code == 200
    assert "Pillar 1: XGBoost (Binary)" in b_res.json()
    assert "Stacked Heterogeneous Ensemble" in b_res.json()

    # Shift Handover (HTML)
    h_res = client.get("/api/v1/reports/shift-handover")
    assert h_res.status_code == 200
    assert "text/html" in h_res.headers["content-type"]
    assert "Tennessee Eastman Process Handover" in h_res.text

    # Shift Handover (JSON)
    j_res = client.get("/api/v1/reports/shift-handover?format=json")
    assert j_res.status_code == 200
    assert "active_alarms_count" in j_res.json()


def test_websocket_telemetry_streaming():
    """Verify live WebSocket telemetry stream delivers valid TelemetryFrame schema."""
    with client.websocket_connect("/ws/telemetry") as websocket:
        # Receive first live frame
        frame_str = websocket.receive_text()
        frame = json.loads(frame_str)

        # Validate schema fields
        assert "run_id" in frame
        assert "step" in frame
        assert "readings" in frame
        assert len(frame["readings"]) == 52, f"Expected 52 sensor readings, got {len(frame['readings'])}"
        assert "risk_score" in frame
        assert 0.0 <= frame["risk_score"] <= 1.0
        assert "health_index" in frame
        assert "regime" in frame
        assert frame["regime"] in ["NORMAL", "WARNING", "CRITICAL"]
        assert "unit_attributions_pct" in frame
        assert "top_fault_id" in frame
        assert "top_3_faults" in frame
        assert len(frame["top_3_faults"]) == 3
        assert "sensor_health_score" in frame
        assert "ttc" in frame
        assert "pillar_scores" in frame
        assert "xgb" in frame["pillar_scores"]
        assert "anomaly" in frame["pillar_scores"]
