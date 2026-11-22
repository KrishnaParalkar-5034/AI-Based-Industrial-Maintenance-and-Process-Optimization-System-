"""
Unit & Anti-Leakage Tests for Causal Data Pipeline and Signal Quality Monitor.
"""
import numpy as np
import pandas as pd
import pytest

from ml.config import TEP_SENSORS
from ml.data_pipeline import build_dataset, clean_causal, compute_causal_features
from ml.signal_quality import check_signal_quality


def test_zero_leakage_split_geometry():
    """Verify strictly zero simulationRun overlap between train, validation, and test splits."""
    ds = build_dataset(max_runs_per_fault=4, test_size=0.25, val_size=0.25, seed=42)

    train_runs = set(ds["train"]["run_id"].unique())
    val_runs = set(ds["val"]["run_id"].unique())
    test_runs = set(ds["test"]["run_id"].unique())

    # Disjoint sets assertion
    assert train_runs.isdisjoint(val_runs), "Data leakage detected: Train and Val splits share run_ids!"
    assert train_runs.isdisjoint(test_runs), "Data leakage detected: Train and Test splits share run_ids!"
    assert val_runs.isdisjoint(test_runs), "Data leakage detected: Val and Test splits share run_ids!"
    assert len(train_runs) > 0 and len(val_runs) > 0 and len(test_runs) > 0


def test_strict_temporal_causality():
    """Verify that modifying future samples in a run NEVER changes past features (strictly causal)."""
    # Create two synthetic runs
    sensors = TEP_SENSORS[:5]
    n_samples = 40
    data = np.ones((n_samples, len(sensors)), dtype=np.float32) * 50.0

    df1 = pd.DataFrame(data, columns=sensors)
    df1["run_id"] = "RUN_01"
    df1["sample"] = np.arange(n_samples)
    df1["fault_flag"] = 0

    # Version 2: Identical up to sample 20, but with massive corruption in the future (samples 21-39)
    df2 = df1.copy()
    df2.loc[21:, sensors] = 9999.0

    feat1 = compute_causal_features(df1, sensors, w_short=5, w_med=15)
    feat2 = compute_causal_features(df2, sensors, w_short=5, w_med=15)

    # Features up to sample 20 must be EXACTLY bit-for-bit identical
    feat_cols = [c for c in feat1.columns if c not in ("run_id", "sample", "fault_flag")]
    diff = np.max(np.abs(feat1.loc[:20, feat_cols].values - feat2.loc[:20, feat_cols].values))

    assert diff == 0.0, f"Acausal feature leakage detected! Past features changed by {diff} when future was modified."


def test_signal_quality_monitor_detections():
    """Verify frozen sensor and spike detection logic."""
    sensors = ["s1", "s2", "s3"]
    # 15 samples: s1 normal varying, s2 frozen flat, s3 has an extreme spike at the end
    n = 15
    data = {
        "s1": np.linspace(10.0, 15.0, n),
        "s2": np.ones(n) * 42.0, # FROZEN
        "s3": np.linspace(20.0, 21.0, n)
    }
    df = pd.DataFrame(data)
    # Inject extreme spike into s3 at current sample
    df.loc[n - 1, "s3"] = 500.0

    normal_mean = pd.Series({"s1": 12.0, "s2": 42.0, "s3": 20.0})
    normal_std = pd.Series({"s1": 2.0, "s2": 1.0, "s3": 1.5})

    result = check_signal_quality(df, sensors, normal_mean, normal_std, frozen_window=10, z_spike_thresh=8.0)

    assert "s2" in result["frozen_channels"], "Failed to detect frozen sensor s2!"
    assert "s3" in result["spike_channels"], "Failed to detect extreme spike on sensor s3!"
    assert result["sensor_health_score"] < 100.0
