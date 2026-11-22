"""
Unit & Integration Tests for 3-Pillar Ensemble, PyTorch Forward Passes, ISA-18.2 Alarms & TreeSHAP.
"""
import os
import joblib
import numpy as np
import pytest
import torch

from ml.alarms import ISA18AlarmManager
from ml.config import PID_UNITS, SENSOR_LABELS, TEP_SENSORS
from ml.explainability import compute_exact_shap_attributions, compute_time_to_critical
from ml.models import DenseAutoencoder, LSTMFCNNet


def test_pytorch_architectures_forward_shapes():
    """Verify PyTorch LSTM-FCN and DenseAutoencoder forward pass dimensions on CPU."""
    batch_size = 8
    seq_len = 20
    n_features = 156 # 52 sensors * 3 (raw, rmean, rstd) approx

    # 1. LSTM-FCN test
    lstm_fcn = LSTMFCNNet(n_features=n_features, hidden_dim=32)
    lstm_fcn.eval()
    dummy_seq = torch.randn(batch_size, seq_len, n_features)
    with torch.no_grad():
        out_seq = lstm_fcn(dummy_seq)
    assert out_seq.shape == (batch_size,), f"Expected output shape ({batch_size},), got {out_seq.shape}"

    # 2. Autoencoder test
    ae = DenseAutoencoder(n_features=n_features)
    ae.eval()
    dummy_flat = torch.randn(batch_size, n_features)
    with torch.no_grad():
        out_ae = ae(dummy_flat)
    assert out_ae.shape == (batch_size, n_features), f"Autoencoder output shape mismatch: {out_ae.shape}"


def test_isa18_alarm_hysteresis_transitions():
    """Verify stateful hysteresis deadband transitions."""
    alarm_mgr = ISA18AlarmManager(warn_enter=0.70, warn_clear=0.62, crit_enter=0.85, crit_clear=0.77)

    # 1. Start in NORMAL
    r1 = alarm_mgr.evaluate_step(risk=0.50, step=0)
    assert r1["regime"] == "NORMAL"

    # 2. Cross into WARNING at 0.72
    r2 = alarm_mgr.evaluate_step(risk=0.72, step=1)
    assert r2["regime"] == "WARNING"
    assert r2["new_alarm_raised"] is True

    # 3. Fluctuate to 0.68 (below 0.70, but ABOVE clear threshold 0.62) -> MUST REMAIN WARNING
    r3 = alarm_mgr.evaluate_step(risk=0.68, step=2)
    assert r3["regime"] == "WARNING", "Hysteresis failed! Dropped to NORMAL before crossing warn_clear (0.62)."

    # 4. Drop below warn_clear to 0.60 -> Returns to NORMAL
    r4 = alarm_mgr.evaluate_step(risk=0.60, step=3)
    assert r4["regime"] == "NORMAL"

    # 5. Jump into CRITICAL at 0.88
    r5 = alarm_mgr.evaluate_step(risk=0.88, step=4)
    assert r5["regime"] == "CRITICAL"

    # 6. Drop to 0.80 (below crit_enter 0.85, but ABOVE crit_clear 0.77) -> MUST REMAIN CRITICAL
    r6 = alarm_mgr.evaluate_step(risk=0.80, step=5)
    assert r6["regime"] == "CRITICAL", "Hysteresis failed! Dropped out of CRITICAL before crossing crit_clear (0.77)."


def test_time_to_critical_calculation():
    """Verify linear slope extrapolation for Time-To-Critical estimation."""
    # Linearly rising risk from 0.70 to 0.79 across 10 samples (slope = 0.01 per sample)
    risk_history = np.linspace(0.70, 0.79, 10)
    curr_risk = 0.79

    res = compute_time_to_critical(
        risk_history,
        current_risk=curr_risk,
        warn_threshold=0.70,
        crit_threshold=0.85,
        sample_interval_min=3.0
    )

    assert res["ttc_active"] is True
    # Delta to critical: 0.85 - 0.79 = 0.06. At slope ~0.01, est_samples = 6 samples
    assert 5 <= res["ttc_samples"] <= 7
    # 6 samples * 3 min = 18 min
    assert 15.0 <= res["ttc_minutes"] <= 21.0


def test_production_artifacts_load_and_infer():
    """Verify saved models/bundle.joblib, lstm_fcn.pt, and autoencoder.pt load cleanly on CPU and produce non-NaN inferences."""
    models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    bundle_path = os.path.join(models_dir, "bundle.joblib")
    lstm_path = os.path.join(models_dir, "lstm_fcn.pt")
    ae_path = os.path.join(models_dir, "autoencoder.pt")

    assert os.path.exists(bundle_path), f"Bundle not found at {bundle_path}"
    assert os.path.exists(lstm_path), f"LSTM-FCN model not found at {lstm_path}"
    assert os.path.exists(ae_path), f"Autoencoder model not found at {ae_path}"

    # 1. Load bundle
    bundle = joblib.load(bundle_path)
    features = bundle["features"]
    n_features = len(features)
    assert n_features == 364, f"Expected 364 engineered features, got {n_features}"

    # 2. Load PyTorch models onto CPU
    lstm_fcn = LSTMFCNNet(n_features=n_features, hidden_dim=64)
    lstm_fcn.load_state_dict(torch.load(lstm_path, map_location="cpu"))
    lstm_fcn.eval()

    autoencoder = DenseAutoencoder(n_features=n_features)
    autoencoder.load_state_dict(torch.load(ae_path, map_location="cpu"))
    autoencoder.eval()

    # 3. Simulate input features
    dummy_x = np.random.randn(1, n_features).astype(np.float32)
    dummy_seq = np.random.randn(1, 20, n_features).astype(np.float32)

    # 4. Pillar 1: XGBoost binary & multiclass
    cal_xgb = bundle.get("xgb_calibrated", bundle["xgb_binary"])
    p_xgb = float(cal_xgb.predict_proba(dummy_x)[0, 1])
    assert 0.0 <= p_xgb <= 1.0 and not np.isnan(p_xgb)

    multi_probs = bundle["xgb_multi"].predict_proba(dummy_x)[0]
    assert len(multi_probs) >= 21
    assert not np.isnan(multi_probs).any()
    assert abs(np.sum(multi_probs) - 1.0) < 1e-4

    # 5. Pillar 2: LSTM-FCN
    with torch.no_grad():
        p_lstm = float(torch.sigmoid(lstm_fcn(torch.from_numpy(dummy_seq)))[0].item())
    assert 0.0 <= p_lstm <= 1.0 and not np.isnan(p_lstm)

    # 6. Pillar 3: Autoencoder
    with torch.no_grad():
        xt = torch.from_numpy(dummy_x)
        mse = float(torch.mean((autoencoder(xt) - xt) ** 2).item())
    lo = bundle["ae_bounds"]["lo"]
    hi = bundle["ae_bounds"]["hi"]
    p_anom = float(np.clip((mse - lo) / (hi - lo + 1e-6), 0.0, 1.0))
    assert 0.0 <= p_anom <= 1.0 and not np.isnan(p_anom)

    # 7. Stacking Meta-Learner
    if getattr(bundle["meta_learner"], "n_features_in_", 3) == 4 and "xgb_multi" in bundle:
        multi_probs = bundle["xgb_multi"].predict_proba(dummy_x)[0]
        p_multi = float(np.clip(1.0 - multi_probs[0], 0.0, 1.0))
        meta_x = np.column_stack([[p_xgb], [p_lstm], [p_anom], [p_multi]])
    else:
        meta_x = np.column_stack([[p_xgb], [p_lstm], [p_anom]])
    p_stacked = float(bundle["meta_learner"].predict_proba(meta_x)[0, 1])
    assert 0.0 <= p_stacked <= 1.0 and not np.isnan(p_stacked)

    # 8. TreeSHAP feature attributions
    shap_res = compute_exact_shap_attributions(bundle["xgb_binary"], features, dummy_x[0], top_k=6)
    assert len(shap_res["top_drivers"]) == 6
    assert shap_res["primary_contributing_unit"] in PID_UNITS
    assert sum(shap_res["unit_attributions_pct"].values()) > 0

