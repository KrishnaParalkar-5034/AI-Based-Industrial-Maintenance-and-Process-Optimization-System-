"""
Signal Quality Monitor for Industrial Process Telemetry.
Flags frozen sensors, NaN/missing values, and extreme statistical outliers (|z| > 8.0).
Computes a composite Sensor Health Score (0-100%).
"""
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


def check_signal_quality(
    window_df: pd.DataFrame,
    sensors: List[str],
    normal_mean: pd.Series,
    normal_std: pd.Series,
    frozen_window: int = 10,
    z_spike_thresh: float = 8.0
) -> Dict[str, Any]:
    """
    Evaluate sensor data quality over a sliding window (or current slice):
      1. Frozen sensor: standard deviation == 0 over last `frozen_window` samples.
      2. Missing / NaN values.
      3. Out-of-bounds spike: |z-score| > z_spike_thresh.
    
    Returns:
      sensor_health_score: float in [0.0, 100.0]
      channel_flags: Dict[str, List[str]]
      frozen_channels: List[str]
      spike_channels: List[str]
      nan_channels: List[str]
    """
    n_samples = len(window_df)
    channel_flags: Dict[str, List[str]] = {}
    frozen_channels: List[str] = []
    spike_channels: List[str] = []
    nan_channels: List[str] = []

    # Take trailing window for frozen check
    sub = window_df.iloc[-min(n_samples, frozen_window):][sensors] if n_samples > 0 else window_df[sensors]

    total_channels = len(sensors)
    healthy_count = 0

    # Current sample (last row) for instantaneous checks
    curr_row = window_df.iloc[-1][sensors] if n_samples > 0 else None

    for s in sensors:
        flags = []
        # NaN check
        if curr_row is not None and pd.isna(curr_row[s]):
            flags.append("NAN_DROPOUT")
            nan_channels.append(s)

        # Frozen sensor check (only if we have >= 3 samples to assess variance)
        if len(sub) >= 3:
            s_std = float(sub[s].std(ddof=1))
            if np.isclose(s_std, 0.0, atol=1e-7):
                flags.append("FROZEN")
                frozen_channels.append(s)

        # Spike / extreme outlier check
        if curr_row is not None and s in normal_mean and s in normal_std and not pd.isna(curr_row[s]):
            mu = float(normal_mean[s])
            sig = float(normal_std[s]) + 1e-6
            z = abs(float(curr_row[s]) - mu) / sig
            if z > z_spike_thresh:
                flags.append(f"SPIKE (|z|={z:.1f})")
                spike_channels.append(s)

        if not flags:
            healthy_count += 1
            channel_flags[s] = []
        else:
            channel_flags[s] = flags

    health_score = round(100.0 * (healthy_count / max(1, total_channels)), 1)

    return {
        "sensor_health_score": health_score,
        "healthy_channels_count": healthy_count,
        "total_channels": total_channels,
        "frozen_channels": frozen_channels,
        "spike_channels": spike_channels,
        "nan_channels": nan_channels,
        "channel_flags": channel_flags,
    }
