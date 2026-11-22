"""
Real-Time Explainability (TreeSHAP), Physical P&ID Unit Attribution & Prescriptive Advice.
Computes fast exact TreeSHAP contributions from XGBoost, aggregates attributions
into the 6 P&ID physical units, and calculates Estimated Time-to-Critical (TTC).
"""
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb

from .config import (
    CRIT_ENTER,
    PID_UNITS,
    SAMPLE_INTERVAL_MIN,
    SENSOR_LABELS,
    SENSOR_TO_UNIT,
    TEP_FAULT_DEFINITIONS,
    TTC_TREND_WINDOW,
    WARN_ENTER,
)


def format_feature_display_name(feat: str) -> Tuple[str, str]:
    """
    Format raw feature name into a clean human-readable name and engineering descriptor.
    Accurately maps causal rolling windows:
      _m30 -> (30-sample mean)
      _s30 -> (30-sample std)
      _m10 -> (10-sample mean)
      _s10 -> (10-sample std)
      _d1  -> (1-step delta)
      _slope -> (trend slope)
    """
    suffix = ""
    base = feat
    if feat.endswith("_m30"):
        base, suffix = feat[:-4], " (30-sample mean)"
    elif feat.endswith("_s30"):
        base, suffix = feat[:-4], " (30-sample std)"
    elif feat.endswith("_m10"):
        base, suffix = feat[:-4], " (10-sample mean)"
    elif feat.endswith("_s10"):
        base, suffix = feat[:-4], " (10-sample std)"
    elif feat.endswith("_d1"):
        base, suffix = feat[:-3], " (1-step delta)"
    elif feat.endswith("_slope"):
        base, suffix = feat[:-6], " (trend slope)"

    readable_sensor = SENSOR_LABELS.get(base, base)
    display_name = f"{readable_sensor}{suffix}"
    return readable_sensor, display_name


def compute_exact_shap_attributions(
    xgb_model: Any,
    feature_names: List[str],
    scaled_row: np.ndarray,
    top_k: int = 10
) -> Dict[str, Any]:
    """
    Compute exact per-sample TreeSHAP feature contributions using XGBoost native predictor.
    Output does not require heavy external C++ shap runtimes.
    """
    booster = xgb_model.get_booster()
    dmat = xgb.DMatrix(scaled_row.reshape(1, -1), feature_names=feature_names)
    # pred_contribs=True returns SHAP values + baseline bias term as the last column
    contribs = booster.predict(dmat, pred_contribs=True)[0]
    base_value = float(contribs[-1])
    shap_values = contribs[:-1]

    # Map back to readable sensor names
    series = pd.Series(shap_values, index=feature_names)
    sorted_series = series.sort_values(key=abs, ascending=False)

    top_drivers = []
    for feat, val in sorted_series.head(top_k).items():
        readable_sensor, display_name = format_feature_display_name(feat)
        unit = SENSOR_TO_UNIT.get(readable_sensor, SENSOR_TO_UNIT.get(feat, "Process Unit"))

        top_drivers.append({
            "feature": feat,
            "display_name": display_name,
            "shap_value": float(round(val, 4)),
            "unit": unit,
            "direction": "Pushes Risk UP" if val > 0 else "Pulls Risk DOWN"
        })

    # Unit-level SHAP aggregation across all 6 P&ID units
    unit_attributions = {u: 0.0 for u in PID_UNITS}
    for feat, val in series.items():
        readable_sensor, _ = format_feature_display_name(feat)
        unit = SENSOR_TO_UNIT.get(readable_sensor, None)
        if unit in unit_attributions:
            unit_attributions[unit] += abs(float(val))

    # Normalize unit percentages
    total_mag = sum(unit_attributions.values()) + 1e-6
    unit_pcts = {u: float(round(100.0 * (v / total_mag), 1)) for u, v in unit_attributions.items()}

    return {
        "base_value": base_value,
        "top_drivers": top_drivers,
        "unit_attributions_raw": unit_attributions,
        "unit_attributions_pct": unit_pcts,
        "primary_contributing_unit": max(unit_pcts, key=unit_pcts.get)
    }


def compute_time_to_critical(
    risk_history: np.ndarray,
    current_risk: float,
    warn_threshold: float = WARN_ENTER,
    crit_threshold: float = CRIT_ENTER,
    window: int = TTC_TREND_WINDOW,
    sample_interval_min: float = SAMPLE_INTERVAL_MIN
) -> Dict[str, Any]:
    """
    Compute Estimated Time-to-Critical (TTC) using trailing linear slope of smoothed risk.
    Only calculated when process is in WARNING regime with a positive risk slope.
    """
    if current_risk < warn_threshold or current_risk >= crit_threshold:
        return {
            "ttc_active": False,
            "slope_per_sample": 0.0,
            "ttc_samples": None,
            "ttc_minutes": None,
            "message": "Process outside Warning transition regime."
        }

    n = len(risk_history)
    k = min(n, window)
    if k < 4:
        return {
            "ttc_active": False,
            "slope_per_sample": 0.0,
            "ttc_samples": None,
            "ttc_minutes": None,
            "message": "Insufficient trend history (< 4 samples)."
        }

    y = risk_history[-k:]
    x = np.arange(k)
    # Simple linear regression: slope = cov(x,y)/var(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    slope = float(np.sum((x - x_mean) * (y - y_mean)) / (np.sum((x - x_mean)**2) + 1e-9))

    if slope <= 1e-4: # Flat or decreasing risk
        return {
            "ttc_active": False,
            "slope_per_sample": round(slope, 5),
            "ttc_samples": None,
            "ttc_minutes": None,
            "message": "Elevated risk is currently stable or declining."
        }

    delta_to_crit = crit_threshold - current_risk
    est_samples = delta_to_crit / slope
    est_minutes = est_samples * sample_interval_min

    return {
        "ttc_active": True,
        "slope_per_sample": round(slope, 5),
        "ttc_samples": int(round(est_samples)),
        "ttc_minutes": round(est_minutes, 1),
        "message": f"Estimated {round(est_minutes, 0):.0f} min until Critical threshold."
    }


def generate_prescriptive_actions(
    fault_id: int,
    primary_unit: str,
    top_drivers: List[Dict[str, Any]],
    regime: str
) -> Dict[str, Any]:
    """
    Synthesize operational prescriptive recommendations based on diagnosed fault mode,
    highest-contributing physical P&ID unit, and active ISA-18.2 severity regime.
    """
    # 1. Normal Operating State: Clean calm status without alarming checklists
    if regime == "NORMAL" or (fault_id == 0 and regime != "CRITICAL"):
        return {
            "urgency": "NOMINAL",
            "diagnosed_fault": "Nominal Operation",
            "action_title": "Nominal Plant Operating State",
            "primary_unit": primary_unit if primary_unit else "All Units",
            "action_steps": [
                "Nominal Operation — No corrective action required.",
                "Process variables and control loops operating within statistical baseline envelopes.",
                "Maintain supervisory monitoring and standard shift inspection log."
            ],
            "recommended_setpoints": {}
        }

    # 2. Disturbance / Elevated Alarm Case
    if fault_id == 0:
        fault_title = "Unclassified Process Anomaly (Novelty Safety Net)"
    else:
        fault_info = TEP_FAULT_DEFINITIONS.get(fault_id, {"name": f"Fault {fault_id}", "type": "Disturbance"})
        fault_title = f"Fault {fault_id}: {fault_info['name']}"

    actions = []
    urgency = "PROACTIVE" if regime == "WARNING" else "IMMEDIATE"

    if regime == "CRITICAL":
        actions.append(f"Notify Shift Supervisor: Confirmed {fault_title} triggering CRITICAL alarm in {primary_unit}.")
        actions.append(f"Dispatch field technician to {primary_unit} to verify local instrumentation.")
    elif regime == "WARNING":
        actions.append(f"Monitor {primary_unit} deviation trend; prepare inspection window before shift handover.")

    # Unit-specific engineering recommendations
    if "Reactor" in primary_unit:
        actions.append("Review reactor cooling water flow (XMV-10) and verify agitator power draw.")
        actions.append("Confirm reactor pressure (XMEAS-7) and temperature (XMEAS-9) operating window.")
    elif "Condenser" in primary_unit:
        actions.append("Inspect condenser cooling water valve (XMV-11) for stiction or heat transfer degradation.")
    elif "Feed" in primary_unit:
        actions.append("Verify reactant feed ratios (A, D, E streams) and check for supply pressure fluctuations.")
    elif "Stripper" in primary_unit:
        actions.append("Check stripper steam flow valve (XMV-9) and column differential pressure.")
    elif "Compressor" in primary_unit:
        actions.append("Inspect recycle compressor vibration, lube oil temperature, and recycle bypass valve (XMV-5).")
    elif "Separator" in primary_unit:
        actions.append("Verify liquid underflow valve (XMV-7) and check interface level sensor calibration.")

    # Driver-level specific action (clean formatted feature name)
    if top_drivers:
        d1 = top_drivers[0].get("display_name", top_drivers[0]["feature"])
        actions.append(f"Highest contributing variable: '{d1}' ({top_drivers[0]['direction']}).")

    return {
        "urgency": urgency,
        "diagnosed_fault": fault_title,
        "action_title": fault_title,
        "primary_unit": primary_unit,
        "action_steps": actions,
        "recommended_setpoints": {}
    }
