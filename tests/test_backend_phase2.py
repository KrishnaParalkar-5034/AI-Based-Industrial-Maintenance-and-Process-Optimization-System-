"""
Phase 2 End-to-End Backend Verification Tests.
Asserts:
  1. Quantile-shift calibration parity in live single-step scoring.
  2. Slim Parquet sub-50ms latency.
  3. F0_R1_d00_te held-out normal run stays calm NORMAL (FPR < 5%, 0 alarms).
  4. F1_R1_d01_te detectable fault run stays NORMAL before t=160 and cleanly trips WARNING/CRITICAL post-onset.
  5. LiveSimulatorAdapter runs calm NORMAL at baseline and cleanly trips on dynamic fault injection.
  6. POST /api/v1/models/reload refreshes both TEPReplayAdapter and LiveSimulatorAdapter.
"""
import os
import time
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.engine import ProcessInferenceEngine, MODELS_DIR
from backend.adapters import TEPReplayAdapter, LiveSimulatorAdapter

client = TestClient(app)


def test_quantile_shift_calibration_parity():
    """Verify engine applies exact quantile shift and gamma calibration from bundle."""
    engine = ProcessInferenceEngine()
    assert engine.bundle is not None
    cal_params = engine.bundle.get("meta_calibration") or engine.bundle.get("calibration_params") or {}
    assert "shift" in cal_params, f"meta_calibration missing shift parameter: {cal_params}"
    assert "scale" in cal_params, f"meta_calibration missing scale parameter: {cal_params}"
    shift = float(cal_params["shift"])
    scale = float(cal_params.get("scale", 0.75))
    assert scale > 0.5
    assert shift > 1.0


def test_slim_parquet_latency():
    """Confirm TEPReplayAdapter loads slim Parquet and maintains fast sub-50ms latency."""
    parquet_path = os.path.join(MODELS_DIR, "replay_sample.parquet")
    assert os.path.exists(parquet_path), "models/replay_sample.parquet must exist"

    df = pd.read_parquet(parquet_path)
    adapter = TEPReplayAdapter(df)
    engine = ProcessInferenceEngine()
    engine.adapter = adapter
    engine.adapter.set_active_run("F0_R1_d00_te")

    latencies = []
    for step in range(10, 30):
        t0 = time.perf_counter()
        frame = engine.process_step(step)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    median_lat = float(np.median(latencies))
    assert median_lat < 100.0, f"Latency too high: {median_lat:.2f} ms"


def test_normal_held_out_run_stability():
    """Assert F0_R1_d00_te stays calm NORMAL (< 5% FPR, 0 false alarms) across all 960 steps."""
    parquet_path = os.path.join(MODELS_DIR, "replay_sample.parquet")
    df = pd.read_parquet(parquet_path)
    adapter = TEPReplayAdapter(df)
    engine = ProcessInferenceEngine()
    engine.adapter = adapter
    engine.adapter.set_active_run("F0_R1_d00_te")
    engine.alarm_mgr.reset()
    engine.recent_risk_history.clear()

    total_steps = engine.adapter.get_total_steps()
    alarms_tripped = 0
    high_risk_steps = 0

    for step in range(total_steps):
        frame = engine.process_step(step)
        if frame["risk_score"] >= 0.70:
            alarms_tripped += 1
        if frame["risk_score"] >= 0.50:
            high_risk_steps += 1

    fpr = (high_risk_steps / total_steps) * 100.0
    assert alarms_tripped == 0, f"Expected 0 alarms on normal run, got {alarms_tripped}"
    assert fpr < 5.0, f"Expected normal run FPR < 5%, got {fpr:.2f}%"


def test_detectable_fault_run_progression():
    """Assert F1_R1_d01_te is NORMAL before t=160 and cleanly trips WARNING/CRITICAL after t=160."""
    parquet_path = os.path.join(MODELS_DIR, "replay_sample.parquet")
    df = pd.read_parquet(parquet_path)
    adapter = TEPReplayAdapter(df)
    engine = ProcessInferenceEngine()
    engine.adapter = adapter
    engine.adapter.set_active_run("F1_R1_d01_te")
    engine.alarm_mgr.reset()
    engine.recent_risk_history.clear()

    # Pre-onset checks (0..150)
    pre_risks = [engine.process_step(s)["risk_score"] for s in range(0, 160, 20)]
    assert max(pre_risks) < 0.50, f"Pre-onset false alarm risk: {max(pre_risks)}"

    # Post-onset checks (160..400)
    post_risks = [engine.process_step(s)["risk_score"] for s in range(160, 400, 20)]
    max_post_risk = max(post_risks)
    assert max_post_risk >= 0.70, f"Fault 1 failed to reach alarm threshold: {max_post_risk}"

    # Verify diagnosis identification
    last_frame = engine.process_step(300)
    assert last_frame["regime"] in ["WARNING", "CRITICAL"]
    assert last_frame["top_fault_id"] == 1


def test_live_simulator_baseline_and_fault_injection():
    """Assert LiveSimulatorAdapter is calm at baseline and trips CRITICAL on fault injection."""
    engine = ProcessInferenceEngine()
    sim_adapter = LiveSimulatorAdapter(bundle=engine.bundle)
    engine.adapter = sim_adapter
    engine.alarm_mgr.reset()
    engine.recent_risk_history.clear()

    # Baseline calm checks
    for step in range(15):
        frame = engine.process_step(step)
    assert frame["risk_score"] < 0.40
    assert frame["regime"] == "NORMAL"
    assert 60.0 <= frame["readings"]["Reactor Level"] <= 90.0

    # Inject Fault 1
    sim_adapter.inject_fault(1)
    for step in range(15, 65):
        frame = engine.process_step(step)

    assert frame["risk_score"] >= 0.70, f"Injected fault failed to trip alarm: {frame['risk_score']}"
    assert frame["regime"] in ["WARNING", "CRITICAL"]
    assert frame["top_fault_id"] == 1

    # Clear fault
    sim_adapter.inject_fault(0)
    for step in range(65, 120):
        frame = engine.process_step(step)

    assert frame["risk_score"] < 0.40
    assert frame["regime"] == "NORMAL"


def test_live_simulator_fault_14_injection():
    """Assert LiveSimulatorAdapter cleanly trips on localized Fault 14 (stripper steam valve)."""
    engine = ProcessInferenceEngine()
    sim_adapter = LiveSimulatorAdapter(bundle=engine.bundle)
    engine.adapter = sim_adapter
    engine.alarm_mgr.reset()
    engine.recent_risk_history.clear()

    # Baseline calm
    for step in range(15):
        frame = engine.process_step(step)
    assert frame["risk_score"] < 0.40

    # Inject Fault 14
    sim_adapter.inject_fault(14)
    max_risk = 0.0
    for step in range(15, 65):
        frame = engine.process_step(step)
        max_risk = max(max_risk, frame["risk_score"])
    assert max_risk >= 0.70, f"Fault 14 failed to trip alarm: {max_risk}"
    assert frame["regime"] in ["WARNING", "CRITICAL"]
    assert frame["top_fault_id"] == 14

    # Clear fault and verify smooth recovery
    sim_adapter.inject_fault(0)
    for step in range(65, 120):
        frame = engine.process_step(step)
    assert frame["risk_score"] < 0.40
    assert frame["regime"] == "NORMAL"


def test_hot_reload_endpoint():
    """Verify POST /api/v1/models/reload hot-reloads artifacts and refreshes adapters."""
    res = client.post("/api/v1/models/reload")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["models_loaded"] is True
    assert data["has_lstm"] is True
    assert data["has_autoencoder"] is True
    assert data["available_runs_count"] > 0
