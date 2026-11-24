"""
Pluggable Telemetry Adapter Layer for TEP Predictive Maintenance.
Provides an extensible abstraction for OPC UA, MQTT, Historical Replay, and Live Simulation.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ml.config import TEP_SENSORS, TEP_SENSOR_NAMES
from ml.data_pipeline import compute_causal_features
import os
import joblib


class BaseTelemetryAdapter(ABC):
    """Abstract base adapter for telemetry data feeds."""

    @abstractmethod
    def get_available_runs(self) -> List[str]:
        pass

    @abstractmethod
    def set_active_run(self, run_id: str) -> bool:
        pass

    @abstractmethod
    def get_current_run_id(self) -> str:
        pass

    @abstractmethod
    def get_step_data(self, step: int) -> Tuple[pd.Series, pd.DataFrame, Optional[int]]:
        """Return (current_row, trailing_window_df, onset_step)."""
        pass

    @abstractmethod
    def get_total_steps(self) -> int:
        pass


class TEPReplayAdapter(BaseTelemetryAdapter):
    """
    Replay adapter streaming pre-computed held-out TEP test runs (real or synthetic).
    Supports time scrubbing, jumping, switching between runs, and a built-in
    cyclic standard demo scenario (Normal -> Warning -> Critical -> Recovery -> Normal).
    """
    def __init__(self, test_df: pd.DataFrame, window_len: int = 50):
        self.test_df = test_df.copy()
        self.window_len = window_len
        self.runs = sorted(self.test_df["run_id"].unique())
        self._demo_cycle_df: Optional[pd.DataFrame] = None
        
        # Build Standard Demo Cycle if F0 and F1 exist
        has_f0 = "F0_R1_d00_te" in self.test_df["run_id"].values
        has_f1 = "F1_R1_d01_te" in self.test_df["run_id"].values
        if has_f0 and has_f1:
            try:
                sub_f0 = self.test_df[self.test_df["run_id"] == "F0_R1_d00_te"].sort_values("sample").reset_index(drop=True)
                sub_f1 = self.test_df[self.test_df["run_id"] == "F1_R1_d01_te"].sort_values("sample").reset_index(drop=True)
                part1 = sub_f0.iloc[20:45].copy()    # 25 normal baseline steps
                part2 = sub_f1.iloc[170:190].copy()  # 20 incipient drift & critical steps
                part3 = sub_f0.iloc[45:90].copy()    # 45 simulated recovery & stabilization steps
                cycle_raw = pd.concat([part1, part2, part3], ignore_index=True)
                cycle_raw["sample"] = np.arange(len(cycle_raw), dtype=int)
                cycle_raw["run_id"] = "STANDARD_DEMO_CYCLE"
                sensor_cols = [c for c in TEP_SENSOR_NAMES if c in cycle_raw.columns]
                self._demo_cycle_df = compute_causal_features(cycle_raw, sensor_cols)
                self.runs = ["STANDARD_DEMO_CYCLE"] + [r for r in self.runs if r != "STANDARD_DEMO_CYCLE"]
            except Exception as ex:
                print(f"[TEPReplayAdapter] Standard demo cycle build deferred: {ex}")

        self.current_run_id: str = self.runs[0] if self.runs else "RUN_00"
        self._cached_run_df: pd.DataFrame = pd.DataFrame()
        self._onset_step: Optional[int] = None
        self._load_cached_run()

    def _load_cached_run(self):
        if self.current_run_id == "STANDARD_DEMO_CYCLE" and self._demo_cycle_df is not None:
            self._cached_run_df = self._demo_cycle_df
            self._onset_step = 25
            return

        sub = self.test_df[self.test_df["run_id"] == self.current_run_id].sort_values("sample").reset_index(drop=True)
        # Compute multi-scale causal features on-the-fly if not precomputed in slim parquet (~40ms once per run)
        has_human_features = "A Feed Flow_m10" in sub.columns
        has_tag_features = "xmeas_1_m10" in sub.columns
        if not has_human_features and not has_tag_features:
            sensor_cols = [c for c in TEP_SENSOR_NAMES if c in sub.columns]
            if not sensor_cols:
                sensor_cols = [c for c in sub.columns if c.startswith(("xmeas_", "xmv_"))]
            if sensor_cols:
                sub = compute_causal_features(sub, sensor_cols)
        self._cached_run_df = sub
        onset_series = sub["sample"][sub["fault_flag"] == 1] if "fault_flag" in sub.columns else pd.Series(dtype=int)
        self._onset_step = int(onset_series.iloc[0]) if len(onset_series) > 0 else None

    def get_available_runs(self) -> List[str]:
        return self.runs

    def set_active_run(self, run_id: str) -> bool:
        if run_id in self.runs:
            self.current_run_id = run_id
            self._load_cached_run()
            return True
        return False

    def get_current_run_id(self) -> str:
        return self.current_run_id

    def get_total_steps(self) -> int:
        return len(self._cached_run_df)

    def get_step_data(self, step: int) -> Tuple[pd.Series, pd.DataFrame, Optional[int]]:
        total = len(self._cached_run_df)
        safe_step = (step % total) if total > 0 else 0
        curr_row = self._cached_run_df.iloc[safe_step]
        # Return trailing window for rolling/frozen checks
        start_idx = max(0, safe_step - self.window_len + 1)
        trailing_df = self._cached_run_df.iloc[start_idx:safe_step + 1]
        return curr_row, trailing_df, self._onset_step


class LiveSimulatorAdapter(BaseTelemetryAdapter):
    """
    Unbounded live AR(1) process simulator capable of on-demand dynamic fault injection.
    Simulates real-time telemetry streaming for continuous plant monitoring.
    """
    def __init__(self, seed: int = 101, bundle: Optional[Dict[str, Any]] = None):
        self.rng = np.random.default_rng(seed)
        self.n_sensors = len(TEP_SENSORS)
        self.replay_df = None
        self._active_fault_df = None
        self.load_baselines(bundle)

        self.current_step = 0
        self.active_fault = 0
        self.injected_onset: Optional[int] = None
        self.history = []
        self._generate_step() # Initial point

    def load_baselines(self, bundle: Optional[Dict[str, Any]] = None):
        """Seed nominal means, stds, and replay benchmark data from bundle / disk."""
        loaded_baselines = False
        if bundle is None:
            bundle_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "bundle.joblib")
            if os.path.exists(bundle_path):
                try:
                    bundle = joblib.load(bundle_path)
                except Exception as e:
                    print(f"[LiveSimulator] Could not load bundle baselines: {e}")

        if bundle is not None:
            m = bundle.get("normal_mean")
            s = bundle.get("normal_std")
            if m is not None and s is not None:
                self.base_means = np.array([float(m[name]) for name in TEP_SENSOR_NAMES], dtype=np.float32)
                self.base_stds = np.array([max(float(s[name]), 0.05) for name in TEP_SENSOR_NAMES], dtype=np.float32)
                self.sim_stds = (self.base_stds * 0.05).astype(np.float32)
                loaded_baselines = True

        if not loaded_baselines:
            self.base_means = self.rng.uniform(10.0, 150.0, size=self.n_sensors).astype(np.float32)
            self.base_means[6] = 2705.0 # Reactor pressure (xmeas_7)
            self.base_means[7] = 75.0   # Reactor level ~75% (xmeas_8)
            self.base_means[8] = 120.4  # Reactor temp (xmeas_9)
            self.base_means[11] = 50.0  # Separator level ~50% (xmeas_12)
            self.base_means[14] = 50.0  # Stripper level ~50% (xmeas_15)
            self.base_means[17] = 65.8  # Stripper temp ~65.8 C (xmeas_18)
            self.base_means[19] = 341.0 # Compressor work (xmeas_20)
            self.base_means[41:52] = 50.0 # Manipulated valves (%)
            self.base_stds = np.maximum(self.base_means * 0.02, 0.25).astype(np.float32)
            self.sim_stds = (self.base_stds * 0.05).astype(np.float32)

        # Attempt caching replay parquet for dynamic fault blending
        parquet_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "replay_sample.parquet")
        if os.path.exists(parquet_path):
            try:
                self.replay_df = pd.read_parquet(parquet_path)
            except Exception as e:
                print(f"[LiveSimulator] Could not load replay_sample.parquet: {e}")

    def _generate_step(self):
        e = self.rng.normal(0, self.sim_stds).astype(np.float32)
        if len(self.history) == 0:
            val = self.base_means + e
        else:
            prev = np.array([self.history[-1][name] for name in TEP_SENSOR_NAMES], dtype=np.float32)
            if self.active_fault > 0 and self._active_fault_df is not None and self.injected_onset is not None:
                rel_step = self.current_step - self.injected_onset
                source_idx = min(160 + rel_step, len(self._active_fault_df) - 1)
                raw_row = np.array([float(self._active_fault_df.iloc[source_idx][name]) for name in TEP_SENSOR_NAMES], dtype=np.float32)
                pre_means = getattr(self, "_pre_onset_means", None)
                if pre_means is None:
                    pre_sub = self._active_fault_df[self._active_fault_df["sample"] < 160]
                    if len(pre_sub) > 0:
                        pre_means = np.array([float(pre_sub[name].mean()) for name in TEP_SENSOR_NAMES], dtype=np.float32)
                    else:
                        pre_means = np.array([float(self._active_fault_df.iloc[0][name]) for name in TEP_SENSOR_NAMES], dtype=np.float32)
                    self._pre_onset_means = pre_means
                delta = raw_row - pre_means
                blend = min(1.0, rel_step / 10.0)
                target_val = self.base_means + delta
                val = (1.0 - blend) * (self.base_means + 0.85 * (prev - self.base_means)) + blend * (target_val + e * 0.2)
            elif self.active_fault > 0 and self.injected_onset is not None:
                ramp = min(1.0, (self.current_step - self.injected_onset) / 15.0)
                affected = [(self.active_fault * 2 + i) % self.n_sensors for i in range(3)]
                val = self.base_means + 0.85 * (prev - self.base_means) + e
                val[affected] += ramp * self.base_stds[affected] * 4.5
            else:
                val = self.base_means + 0.70 * (prev - self.base_means) + e

        # Clamp liquid levels to realistic physical bounds [10.0, 95.0]%
        val[7] = np.clip(val[7], 10.0, 95.0)   # Reactor Level
        val[11] = np.clip(val[11], 10.0, 95.0) # Separator Level
        val[14] = np.clip(val[14], 10.0, 95.0) # Stripper Level

        # Populate both sensor tags (xmeas_*, xmv_*) and human readable names (A Feed Flow, ...)
        row_dict = {}
        for tag, name, v in zip(TEP_SENSORS, TEP_SENSOR_NAMES, val.tolist()):
            row_dict[tag] = v
            row_dict[name] = v

        row_dict["sample"] = self.current_step
        row_dict["run_id"] = "LIVE_STREAM"
        row_dict["fault_class"] = self.active_fault
        row_dict["fault_flag"] = 1 if self.active_fault > 0 else 0
        s = pd.Series(row_dict)
        self.history.append(s)
        self.current_step += 1

    def inject_fault(self, fault_id: int):
        self.active_fault = fault_id
        self.injected_onset = self.current_step
        self._pre_onset_means = None
        if fault_id > 0 and self.replay_df is not None:
            run_id = f"F{fault_id}_R1_d{fault_id:02d}_te"
            sub = self.replay_df[self.replay_df["run_id"] == run_id].sort_values("sample").reset_index(drop=True)
            if len(sub) > 0:
                self._active_fault_df = sub
                pre_sub = sub[sub["sample"] < 160]
                if len(pre_sub) > 0:
                    self._pre_onset_means = np.array([float(pre_sub[name].mean()) for name in TEP_SENSOR_NAMES], dtype=np.float32)
                else:
                    self._pre_onset_means = np.array([float(sub.iloc[0][name]) for name in TEP_SENSOR_NAMES], dtype=np.float32)
            else:
                self._active_fault_df = None
        else:
            self._active_fault_df = None

    def get_available_runs(self) -> List[str]:
        return ["LIVE_STREAM"]

    def set_active_run(self, run_id: str) -> bool:
        return run_id == "LIVE_STREAM"

    def get_current_run_id(self) -> str:
        return "LIVE_STREAM"

    def get_total_steps(self) -> int:
        return max(1000, self.current_step + 100)

    def get_step_data(self, step: int) -> Tuple[pd.Series, pd.DataFrame, Optional[int]]:
        while self.current_step <= step:
            self._generate_step()
        start_idx = max(0, step - 50 + 1)
        trailing_df = pd.DataFrame(self.history[start_idx:step + 1])
        feat_df = compute_causal_features(trailing_df, TEP_SENSOR_NAMES)
        curr_row = feat_df.iloc[-1]
        return curr_row, feat_df, self.injected_onset
