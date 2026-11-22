"""
Automated Contract Compatibility Smoke Test for Frontend Phase 4.
Validates that backend REST endpoints and WebSocket payloads match frontend/src/types.ts.
"""
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_frontend_contract_stream_status():
    res = client.get("/api/v1/stream/status")
    assert res.status_code == 200
    data = res.json()
    required_keys = [
        "is_playing", "speed", "current_run_id", "current_step",
        "total_steps", "active_model_mode", "available_runs", "hysteresis_thresholds"
    ]
    for k in required_keys:
        assert k in data, f"Missing key '{k}' in stream status contract"
    assert "warn_enter" in data["hysteresis_thresholds"]
    assert "crit_enter" in data["hysteresis_thresholds"]


def test_frontend_contract_stream_control_actions():
    # Test all control actions used by Header & Hysteresis drawer
    # 1. Play / Pause
    assert client.post("/api/v1/stream/control", json={"action": "play"}).status_code == 200
    assert client.post("/api/v1/stream/control", json={"action": "pause"}).status_code == 200

    # 2. Speed
    assert client.post("/api/v1/stream/control", json={"action": "speed", "speed": 2.0}).status_code == 200

    # 3. Seek
    assert client.post("/api/v1/stream/control", json={"action": "seek", "step": 10}).status_code == 200

    # 4. Mode - Test all 4 supported model modes
    for mode in ["stacked_ensemble", "xgboost", "lstm_fcn", "anomaly"]:
        assert client.post("/api/v1/stream/control", json={"action": "toggle_mode", "model_mode": mode}).status_code == 200

    # 5. Update hysteresis
    h_res = client.post("/api/v1/stream/control", json={
        "action": "update_hysteresis",
        "warn_enter": 0.72,
        "warn_clear": 0.64,
        "crit_enter": 0.86,
        "crit_clear": 0.78
    })
    assert h_res.status_code == 200


def test_frontend_contract_explainability():
    s_res = client.get("/api/v1/stream/status")
    run_id = s_res.json()["current_run_id"]
    res = client.get(f"/api/v1/explain/{run_id}/5")
    assert res.status_code == 200
    data = res.json()
    for k in ["run_id", "step", "base_value", "top_drivers", "unit_attributions_raw", "unit_attributions_pct", "primary_contributing_unit", "prescriptive_actions"]:
        assert k in data, f"Missing key '{k}' in explainability contract"
    assert isinstance(data["top_drivers"], list)
    assert isinstance(data["unit_attributions_pct"], dict)
    assert "action_steps" in data["prescriptive_actions"]
    assert "diagnosed_fault" in data["prescriptive_actions"]
    assert "primary_unit" in data["prescriptive_actions"]


def test_frontend_contract_alarms_and_handover():
    # 1. Query alarms
    a_res = client.get("/api/v1/alarms?limit=10")
    assert a_res.status_code == 200
    alarms = a_res.json()
    assert isinstance(alarms, list)

    # 2. Benchmarks
    b_res = client.get("/api/v1/models/benchmarks")
    assert b_res.status_code == 200
    b_data = b_res.json()
    assert "Pillar 1: XGBoost (Binary)" in b_data
    assert "Stacked Heterogeneous Ensemble" in b_data

    # 3. Shift Handover JSON
    h_res = client.get("/api/v1/reports/shift-handover?format=json")
    assert h_res.status_code == 200
    h_data = h_res.json()
    for k in ["report_title", "generated_at", "advisory_notice", "active_alarms_count", "resolved_alarms_count", "active_alarms", "audit_logs"]:
        assert k in h_data, f"Missing key '{k}' in shift handover JSON"

    # 4. Shift Handover HTML print-ready
    html_res = client.get("/api/v1/reports/shift-handover?format=html")
    assert html_res.status_code == 200
    assert "Tennessee Eastman" in html_res.text


def test_frontend_contract_websocket_frame():
    with client.websocket_connect("/ws/telemetry") as ws:
        frame_raw = ws.receive_text()
        frame = json.loads(frame_raw)

        expected_fields = [
            "run_id", "step", "total_steps", "timestamp", "model_mode",
            "readings", "deviations_sigma", "channel_flags", "sensor_health_score",
            "risk_score", "health_index", "regime", "alarm_flood", "alarms_in_10min",
            "unit_attributions_pct", "top_fault_id", "top_fault_name", "top_fault_conf",
            "top_3_faults", "ttc", "pillar_scores", "inference_latency_ms", "prescriptive_actions"
        ]
        for field in expected_fields:
            assert field in frame, f"Missing field '{field}' in live telemetry frame WebSocket contract"

        assert isinstance(frame["pillar_scores"], dict)
        assert "ensemble" in frame["pillar_scores"]
        assert "xgb" in frame["pillar_scores"]
        assert "lstm_fcn" in frame["pillar_scores"]
        assert "anomaly" in frame["pillar_scores"]
        assert "ttc_active" in frame["ttc"]
        assert "action_steps" in frame["prescriptive_actions"]
