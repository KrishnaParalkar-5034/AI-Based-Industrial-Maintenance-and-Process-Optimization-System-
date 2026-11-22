"""
Inference & Streaming Coordinator for TEP Predictive Maintenance Backend.
Loads production models, drives telemetry adapters, executes real-time scoring,
evaluates ISA-18.2 hysteresis, TreeSHAP explainability, and persists events to DB.
"""
from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import torch

from ml.alarms import ISA18AlarmManager
from ml.config import PID_UNITS, SENSOR_LABELS, SENSOR_TO_UNIT, TEP_FAULT_DEFINITIONS, TEP_SENSORS
from ml.explainability import (
    compute_exact_shap_attributions,
    compute_time_to_critical,
    generate_prescriptive_actions,
)
from ml.models import DenseAutoencoder, LSTMFCNNet
from ml.signal_quality import check_signal_quality

from .adapters import BaseTelemetryAdapter, LiveSimulatorAdapter, TEPReplayAdapter
from .db import Alarm, AuditLog, SessionLocal, TelemetryEvent

MODELS_DIR = os.environ.get("MODELS_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "models"))


class ProcessInferenceEngine:
    """Singleton inference coordinator managing model weights and active stream state."""

    def __init__(self):
        self.bundle_path = os.path.join(MODELS_DIR, "bundle.joblib")
        self.lstm_path = os.path.join(MODELS_DIR, "lstm_fcn.pt")
        self.ae_path = os.path.join(MODELS_DIR, "autoencoder.pt")

        self.bundle: Optional[Dict[str, Any]] = None
        self.lstm_fcn: Optional[LSTMFCNNet] = None
        self.autoencoder: Optional[DenseAutoencoder] = None

        self.adapter: Optional[BaseTelemetryAdapter] = None
        self.alarm_mgr = ISA18AlarmManager()

        # Playback state
        self.is_playing: bool = False
        self.playback_speed: float = 1.0 # 1 sample per second base
        self.current_step: int = 0
        self.model_mode: str = "stacked_ensemble" # stacked_ensemble, xgboost, anomaly
        self.recent_risk_history: List[float] = []
        self.last_latency_ms: float = 0.0
        self.last_persisted_run_step: Optional[Tuple[str, int]] = None
        self.cached_frame: Optional[Dict[str, Any]] = None
        self.cached_key: Optional[Tuple] = None

        self.load_artifacts()

    def load_artifacts(self) -> bool:
        """Load trained models and scalers into memory."""
        if not os.path.exists(self.bundle_path):
            print(f"[engine] Warning: {self.bundle_path} not found. Run training first.")
            return False

        print(f"[engine] Loading model bundle from {self.bundle_path}...")
        self.bundle = joblib.load(self.bundle_path)

        n_features = len(self.bundle["features"])

        # Load PyTorch models if present
        if os.path.exists(self.ae_path):
            try:
                self.autoencoder = DenseAutoencoder(n_features)
                self.autoencoder.load_state_dict(torch.load(self.ae_path, map_location="cpu", weights_only=True))
                self.autoencoder.eval()
                print("[engine] Loaded Autoencoder successfully.")
            except Exception as e:
                print(f"[engine] Failed to load Autoencoder: {e}")

        if os.path.exists(self.lstm_path):
            try:
                self.lstm_fcn = LSTMFCNNet(n_features)
                self.lstm_fcn.load_state_dict(torch.load(self.lstm_path, map_location="cpu", weights_only=True))
                self.lstm_fcn.eval()
                print("[engine] Loaded LSTM-FCN successfully.")
            except Exception as e:
                print(f"[engine] Failed to load LSTM-FCN: {e}")

        # Initialize replay adapter using replay sample file or held-out test data from bundle
        replay_df = None
        parquet_path = os.path.join(MODELS_DIR, "replay_sample.parquet")
        csv_gz_path = os.path.join(MODELS_DIR, "replay_sample.csv.gz")

        if os.path.exists(parquet_path):
            try:
                replay_df = pd.read_parquet(parquet_path)
                print(f"[engine] Loaded replay_sample.parquet with {replay_df['run_id'].nunique()} runs.")
            except Exception as e:
                print(f"[engine] Failed to load replay_sample.parquet: {e}")

        if replay_df is None and os.path.exists(csv_gz_path):
            try:
                replay_df = pd.read_csv(csv_gz_path, compression="gzip")
                print(f"[engine] Loaded replay_sample.csv.gz with {replay_df['run_id'].nunique()} runs.")
            except Exception as e:
                print(f"[engine] Failed to load replay_sample.csv.gz: {e}")

        test_df = replay_df if replay_df is not None and not replay_df.empty else (self.bundle.get("test") if self.bundle else None)
        if isinstance(self.adapter, LiveSimulatorAdapter):
            self.adapter.load_baselines(self.bundle)
            print("[engine] Refreshed baselines on active LiveSimulatorAdapter.")
        elif test_df is not None and not test_df.empty:
            self.adapter = TEPReplayAdapter(test_df)
            print(f"[engine] Replay adapter initialized with {len(self.adapter.get_available_runs())} runs.")
        else:
            self.adapter = LiveSimulatorAdapter(bundle=self.bundle)
            print("[engine] Initialized with LiveSimulatorAdapter fallback.")

        return True

    def process_step(self, step: int, is_step_advance: bool = True) -> Dict[str, Any]:
        """
        Execute end-to-end inference on specified time step:
          1. Retrieve row and trailing window from adapter.
          2. Check signal quality.
          3. Calculate model scores & multi-class predictions.
          4. Evaluate ISA-18.2 stateful alarms.
          5. Compute unit-level SHAP attributions and TTC.
          6. Persist to DB (only on step advancement to prevent duplicate logs).
        """
        t0 = time.perf_counter()
        if self.bundle is None:
            raise RuntimeError("Engine artifacts not loaded.")

        run_id = self.adapter.get_current_run_id() if self.adapter else ""
        cache_key = (
            run_id,
            step,
            self.model_mode,
            self.alarm_mgr.warn_enter,
            self.alarm_mgr.warn_clear,
            self.alarm_mgr.crit_enter,
            self.alarm_mgr.crit_clear,
        )
        if not is_step_advance and self.cached_frame is not None and cache_key == self.cached_key:
            return self.cached_frame

        curr_row, trailing_df, onset_step = self.adapter.get_step_data(step)
        sensors = self.bundle["sensors"]
        normal_mean = self.bundle["normal_mean"]
        normal_std = self.bundle["normal_std"]

        # 1. Signal Quality Monitor
        sig_result = check_signal_quality(trailing_df, sensors, normal_mean, normal_std)

        # 2. Model Scoring
        feat_cols = self.bundle["features"]
        X_scaled = self.bundle["scaler"].transform(curr_row[feat_cols].values.reshape(1, -1).astype(np.float32))

        # Pillar 1: XGBoost Binary (Calibrated) & Multi-Class Scoring
        cal_xgb = self.bundle.get("xgb_calibrated", self.bundle["xgb_binary"])
        p_xgb = float(cal_xgb.predict_proba(X_scaled)[0, 1])
        multi_probs = self.bundle["xgb_multi"].predict_proba(X_scaled)[0]

        # Pillar 2: LSTM-FCN with 20-step sequence from buffered trailing_df (50 samples buffered)
        if self.lstm_fcn is not None and len(trailing_df) > 0:
            seq_scaled = self.bundle["scaler"].transform(trailing_df[feat_cols].values.astype(np.float32))
            if len(seq_scaled) < 20:
                pad_len = 20 - len(seq_scaled)
                seq_scaled = np.vstack([np.repeat(seq_scaled[0:1], pad_len, axis=0), seq_scaled])
            else:
                seq_scaled = seq_scaled[-20:]
            with torch.no_grad():
                seq_t = torch.from_numpy(seq_scaled.reshape(1, 20, len(feat_cols))).float()
                p_lstm = float(torch.sigmoid(self.lstm_fcn(seq_t))[0].item())
        else:
            p_lstm = p_xgb

        # Pillar 3: Autoencoder Novelty
        if self.autoencoder is not None:
            with torch.no_grad():
                xt = torch.from_numpy(X_scaled).float()
                mse = float(torch.mean((self.autoencoder(xt) - xt)**2).item())
                lo = self.bundle["ae_bounds"]["lo"]
                hi = self.bundle["ae_bounds"]["hi"]
                p_anom = float(np.clip((mse - lo) / (hi - lo + 1e-6), 0.0, 1.0))
        else:
            raw = float(-self.bundle["iso_forest"].score_samples(X_scaled)[0])
            p_anom = float(np.clip(raw, 0.0, 1.0))

        # Selected mode evaluation
        if self.model_mode == "xgboost":
            raw_risk = p_xgb
        elif self.model_mode == "anomaly":
            raw_risk = p_anom
        elif self.model_mode == "lstm_fcn":
            raw_risk = p_lstm
        else: # stacked_ensemble: [P_xgb, P_lstm, P_anom, P_multi_fault]
            if getattr(self.bundle["meta_learner"], "n_features_in_", 3) == 4 and "xgb_multi" in self.bundle:
                p_multi_fault = float(np.clip(1.0 - multi_probs[0], 0.0, 1.0))
                meta_X = np.column_stack([[p_xgb], [p_lstm], [p_anom], [p_multi_fault]])
            else:
                meta_X = np.column_stack([[p_xgb], [p_lstm], [p_anom]])
            cal_params = self.bundle.get("meta_calibration")
            if cal_params and hasattr(self.bundle["meta_learner"], "decision_function"):
                raw = float(self.bundle["meta_learner"].decision_function(meta_X)[0])
                shift = float(cal_params["shift"])
                scale = float(cal_params.get("scale", 0.75))
                raw_risk = float(1.0 / (1.0 + np.exp(-scale * (raw - shift))))
            else:
                raw_risk = float(self.bundle["meta_learner"].predict_proba(meta_X)[0, 1])

        # Smooth risk over trailing window (only advance history if step advanced or empty)
        if is_step_advance or len(self.recent_risk_history) == 0:
            self.recent_risk_history.append(raw_risk)
            if len(self.recent_risk_history) > 30:
                self.recent_risk_history.pop(0)

        smoothed_risk = float(np.mean(self.recent_risk_history[-5:]))
        health_index = float(round(100.0 * (1.0 - smoothed_risk), 1))

        # 3. ISA-18.2 Alarm Manager
        alarm_eval = self.alarm_mgr.evaluate_step(smoothed_risk, step)
        regime = alarm_eval["regime"]

        # Fault Isolation & Diagnosis (Never diagnose Fault 0: Normal on active alarms)
        non_zero_probs = multi_probs[1:]
        best_non_zero_idx = int(np.argmax(non_zero_probs)) + 1
        best_non_zero_conf = float(non_zero_probs[best_non_zero_idx - 1])

        if regime in ["WARNING", "CRITICAL"] or smoothed_risk >= 0.50:
            if best_non_zero_conf >= 0.12:
                top_fault_id = best_non_zero_idx
                top_fault_conf = best_non_zero_conf
                top_fault_name = TEP_FAULT_DEFINITIONS.get(top_fault_id, {}).get("name", f"Fault {top_fault_id}")
            else:
                top_fault_id = best_non_zero_idx
                top_fault_conf = best_non_zero_conf
                top_fault_name = "Unclassified Process Anomaly (Novelty Safety Net)"

            # Top-3 diagnoses prioritizing candidate disturbance physics
            top_3_indices = [int(i) + 1 for i in np.argsort(non_zero_probs)[::-1][:3]]
        else:
            top_fault_id = 0
            top_fault_conf = float(multi_probs[0])
            top_fault_name = "Normal Operation"
            top_3_indices = [int(i) for i in np.argsort(multi_probs)[::-1][:3]]

        top_3_faults = []
        for f_idx in top_3_indices:
            f_info = TEP_FAULT_DEFINITIONS.get(f_idx, {"name": f"Fault {f_idx}"})
            top_3_faults.append({
                "fault_id": int(f_idx),
                "name": f_info["name"],
                "confidence": float(round(multi_probs[f_idx], 3))
            })

        # 4. TreeSHAP & Unit Attribution
        shap_res = compute_exact_shap_attributions(self.bundle["xgb_binary"], feat_cols, X_scaled[0], top_k=8)
        unit_pcts = shap_res["unit_attributions_pct"]
        primary_unit = shap_res["primary_contributing_unit"]

        # 5. Estimated Time-to-Critical (TTC)
        ttc = compute_time_to_critical(np.array(self.recent_risk_history), smoothed_risk)

        # 6. Read-out sensor readings and deviations
        readings = {}
        deviations_sigma = {}
        normal_baselines = {}
        for s in sensors:
            val = float(curr_row[s])
            mu = float(normal_mean[s])
            sig = float(normal_std[s]) + 1e-6
            readings[s] = float(round(val, 2))
            deviations_sigma[s] = float(round((val - mu) / sig, 2))
            normal_baselines[s] = {
                "mean": float(round(mu, 2)),
                "std": float(round(sig, 3))
            }

        # 7. Prescriptive actions
        prescriptive = generate_prescriptive_actions(top_fault_id, primary_unit, shap_res["top_drivers"], regime)

        # 8. Database Persistence (deduplicated: only on step advance or unique step)
        now_dt = datetime.now(timezone.utc)
        run_id = self.adapter.get_current_run_id()
        if is_step_advance or (run_id, step) != self.last_persisted_run_step:
            try:
                with SessionLocal() as db:
                    event = TelemetryEvent(
                        timestamp=now_dt,
                        run_id=run_id,
                        step=step,
                        model_mode=self.model_mode,
                        risk_score=float(round(smoothed_risk, 4)),
                        health_index=health_index,
                        regime=regime,
                        top_fault_id=top_fault_id,
                        top_fault_conf=float(round(top_fault_conf, 3)),
                        sensor_health_score=sig_result["sensor_health_score"]
                    )
                    db.add(event)

                    # If a new alarm is triggered, create persistent alarm entry
                    if alarm_eval["new_alarm_raised"]:
                        alarm_diagnosis_str = (
                            f"Fault {top_fault_id}: {top_fault_name}"
                            if top_fault_name != "Unclassified Process Anomaly (Novelty Safety Net)"
                            else top_fault_name
                        )
                        new_alarm = Alarm(
                            timestamp=now_dt,
                            run_id=run_id,
                            step=step,
                            severity=regime,
                            fault_diagnosis=alarm_diagnosis_str,
                            top_unit=primary_unit,
                            top_shap_drivers_json=json.dumps(shap_res["top_drivers"][:5]),
                            status="ACTIVE"
                        )
                        db.add(new_alarm)
                    db.commit()
                self.last_persisted_run_step = (run_id, step)
            except Exception as exc:
                print(f"[engine] DB logging failed: {exc}")

        self.last_latency_ms = float(round((time.perf_counter() - t0) * 1000.0, 2))

        frame_dict = {
            "run_id": run_id,
            "step": step,
            "total_steps": self.adapter.get_total_steps(),
            "timestamp": now_dt.isoformat(),
            "model_mode": self.model_mode,
            "adapter_type": "simulator" if isinstance(self.adapter, LiveSimulatorAdapter) else "replay",
            "active_fault": getattr(self.adapter, "active_fault", 0) if isinstance(self.adapter, LiveSimulatorAdapter) else 0,
            "readings": readings,
            "deviations_sigma": deviations_sigma,
            "normal_baselines": normal_baselines,
            "channel_flags": sig_result["channel_flags"],
            "sensor_health_score": sig_result["sensor_health_score"],
            "risk_score": float(round(smoothed_risk, 4)),
            "health_index": health_index,
            "regime": regime,
            "alarm_flood": alarm_eval["alarm_flood"],
            "alarms_in_10min": alarm_eval["alarms_in_10min"],
            "unit_attributions_pct": unit_pcts,
            "top_fault_id": top_fault_id,
            "top_fault_name": top_fault_name,
            "top_fault_conf": float(round(top_fault_conf, 3)),
            "top_3_faults": top_3_faults,
            "ttc": ttc,
            "pillar_scores": {
                "xgb": float(round(p_xgb, 4)),
                "lstm_fcn": float(round(p_lstm, 4)),
                "anomaly": float(round(p_anom, 4)),
                "ensemble": float(round(smoothed_risk, 4)),
            },
            "fault_onset_sample": onset_step,
            "inference_latency_ms": self.last_latency_ms,
            "prescriptive_actions": prescriptive
        }

        self.cached_frame = frame_dict
        self.cached_key = cache_key
        return frame_dict

    def reload_models(self) -> Dict[str, Any]:
        """Hot-reload model weights and scalers from disk without restarting service."""
        success = self.load_artifacts()
        self.cached_frame = None
        self.cached_key = None
        self.current_step = 0
        self.alarm_mgr.reset()
        self.recent_risk_history.clear()
        self.last_persisted_run_step = None

        dataset_origin = self.bundle.get("dataset_origin", "synthetic_ar1") if self.bundle else "unknown"
        run_count = len(self.adapter.get_available_runs()) if self.adapter else 0

        return {
            "status": "success" if success else "failed",
            "models_loaded": self.bundle is not None,
            "has_lstm": self.lstm_fcn is not None,
            "has_autoencoder": self.autoencoder is not None,
            "dataset_origin": dataset_origin,
            "available_runs_count": run_count,
            "current_run_id": self.adapter.get_current_run_id() if self.adapter else "LIVE_STREAM",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def switch_adapter(self, adapter_type: str) -> str:
        """Switch active telemetry feed between held-out historical replay and live simulation."""
        adapter_type = adapter_type.lower()
        if adapter_type in ["replay", "historical"]:
            parquet_path = os.path.join(MODELS_DIR, "replay_sample.parquet")
            csv_gz_path = os.path.join(MODELS_DIR, "replay_sample.csv.gz")
            replay_df = None
            if os.path.exists(parquet_path):
                try:
                    replay_df = pd.read_parquet(parquet_path)
                except Exception:
                    pass
            if replay_df is None and os.path.exists(csv_gz_path):
                try:
                    replay_df = pd.read_csv(csv_gz_path, compression="gzip")
                except Exception:
                    pass

            test_df = replay_df if replay_df is not None and not replay_df.empty else (self.bundle.get("test") if self.bundle else None)
            if test_df is not None and not test_df.empty:
                self.adapter = TEPReplayAdapter(test_df)
                mode_desc = f"Historical Replay ({len(self.adapter.get_available_runs())} runs)"
            else:
                self.adapter = LiveSimulatorAdapter(bundle=self.bundle)
                mode_desc = "Live Process Simulator (Fallback)"
        elif adapter_type in ["simulator", "live", "live_sim"]:
            self.adapter = LiveSimulatorAdapter(bundle=self.bundle)
            self.is_playing = True
            mode_desc = "Live AR(1) Process Simulator"
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

        self.current_step = 0
        self.cached_frame = None
        self.cached_key = None
        self.alarm_mgr.reset()
        self.recent_risk_history.clear()
        self.last_persisted_run_step = None
        return mode_desc


# Global singleton instance
engine_instance = ProcessInferenceEngine()
