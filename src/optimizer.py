"""
Stage 4 - Risk assessment & decision support.
Combines classifier probability and anomaly score into a risk score, maps it to
NORMAL / WARNING / CRITICAL and produces recommendations FOR HUMAN REVIEW.
This module never writes to, or controls, any plant system.
"""
import numpy as np
import pandas as pd

from .ml_models import score_frame

WARN_T, CRIT_T = 0.70, 0.85  # tuned on held-out runs; matches the dashboard defaults
W_CLF, W_ANOM = 0.65, 0.35
SMOOTH = 5  # samples; avoids alarm flicker

# keyword in variable name -> (equipment, advice)
# Order matters: the first matching rule wins, so specific plant equipment is listed
# before the generic valve / pump rules ("Stripper Steam Valve" -> Stripper, not "Control valve").
EQUIPMENT_RULES = [
    (("cooling", "coolant", "condenser", "hx_diff"),
     ("Heat exchanger", "Inspect for fouling / scaling; check cooling-water flow and plan a cleaning window.")),
    (("compressor", "recycle"),
     ("Compressor", "Check bearings, vibration trend and recycle valve; review lube-oil condition.")),
    (("reactor",),
     ("Reactor", "Verify instrument calibration and review the reactor operating window with the process engineer.")),
    (("separator",),
     ("Separator", "Verify instrument calibration and review the separator operating window with the process engineer.")),
    (("stripper",),
     ("Stripper", "Verify instrument calibration; check steam supply and review the stripper operating window.")),
    (("composition", "analysis"),
     ("Analyser / stream composition", "Check feed quality and analyser calibration; confirm upstream separation is within spec.")),
    (("valve",),
     ("Control valve", "Run a valve signature / stroke test; check actuator, packing and positioner for stiction.")),
    (("feed", "pump", "viscosity"),
     ("Pump / feed line", "Check pump discharge pressure and motor current; inspect strainers and feed quality.")),
]


def equipment_for(var):
    name = var.lower()          # labels are Title Case, keywords are lower case
    for keys, info in EQUIPMENT_RULES:
        if any(k in name for k in keys):
            return info
    return ("Process unit", "Review trend with the process engineer.")


def status_from_risk(risk, warn_t=WARN_T, crit_t=CRIT_T):
    return np.where(risk >= crit_t, "CRITICAL", np.where(risk >= warn_t, "WARNING", "NORMAL"))


def assess_run(bundle, run_df, warn_t=WARN_T, crit_t=CRIT_T):
    """Score a single run's time series -> DataFrame with risk, health index and status."""
    run_df = run_df.sort_values("sample").reset_index(drop=True)
    p, a = score_frame(bundle, run_df)
    risk = pd.Series(W_CLF * p + W_ANOM * a).rolling(SMOOTH, min_periods=1).mean().values
    out = pd.DataFrame({"sample": run_df["sample"], "p_fail": p, "anomaly": a, "risk": risk})
    out["health_index"] = (100 * (1 - risk)).round(1)
    out["status"] = status_from_risk(risk, warn_t, crit_t)
    return out


def recommendations(bundle, run_df, assessed, t, top_k=3):
    """Explain the state at step t: most deviating variables -> equipment -> suggested action."""
    top_k = max(1, min(top_k, len(bundle["sensors"])))
    run_sorted = run_df.sort_values("sample").reset_index(drop=True)
    row = run_sorted.iloc[t]
    z = ((row[bundle["sensors"]] - bundle["normal_mean"]) / bundle["normal_std"])
    top = z.abs().sort_values(ascending=False).head(top_k).index
    status, risk = assessed["status"].iloc[t], assessed["risk"].iloc[t]
    trend = assessed["risk"].iloc[t] - assessed["risk"].iloc[max(0, t - 10)]
    if status == "CRITICAL":
        timing = "Recommend engineer review NOW and schedule inspection at the next safe opportunity."
    elif status == "WARNING":
        timing = ("Risk is rising - plan inspection within the next shift/maintenance window."
                  if trend > 0.05 else "Elevated but stable - monitor closely and plan inspection this week.")
    else:
        timing = "No action needed. Operating inside the normal window."
    items = []
    for var in top:
        eq, advice = equipment_for(var)
        items.append(dict(variable=var, deviation_sigma=round(float(z[var]), 1), equipment=eq, suggestion=advice))
    return dict(status=status, risk=float(risk), timing=timing, items=pd.DataFrame(items))


SAMPLE_MINUTES = 3  # TEP is sampled every 3 minutes


def early_warning_report(bundle, warn_t=WARN_T, crit_t=CRIT_T):
    """How EARLY the alarm fires, per held-out run.

    For every run we compare the first sample whose status leaves NORMAL with the known
    fault onset (derived from `fault_flag`). A negative delay means the model alarmed
    BEFORE the fault was injected, i.e. a false alarm on a faulty run.
    Returns (summary dict, per-run DataFrame).
    """
    rows = []
    for run_id, run in bundle["test"].groupby("run_id"):
        run = run.sort_values("sample").reset_index(drop=True)
        assessed = assess_run(bundle, run, warn_t, crit_t)
        alerted = assessed["status"] != "NORMAL"
        first_alert = int(run["sample"][alerted].iloc[0]) if alerted.any() else None
        onset = run["sample"][run["fault_flag"] == 1]
        onset = int(onset.iloc[0]) if len(onset) else None
        rows.append(dict(
            run_id=run_id, fault_class=int(run["fault_class"].iloc[0]),
            onset=onset, first_alert=first_alert,
            delay=None if (onset is None or first_alert is None) else first_alert - onset,
        ))
    per_run = pd.DataFrame(rows)

    faulty = per_run[per_run["fault_class"] > 0]
    detected = faulty[faulty["delay"].notna() & (faulty["delay"] >= 0)]
    normal = per_run[per_run["fault_class"] == 0]
    median_delay = float(detected["delay"].median()) if len(detected) else None
    summary = dict(
        faulty_runs=int(len(faulty)),
        detected=int(len(detected)),
        missed=int(len(faulty) - len(detected)),
        pre_onset_false_alarms=int((faulty["delay"] < 0).sum()),
        normal_runs=int(len(normal)),
        normal_false_alarms=int(normal["first_alert"].notna().sum()),
        median_delay_samples=median_delay,
        median_delay_minutes=None if median_delay is None else median_delay * SAMPLE_MINUTES,
        worst_delay_samples=float(detected["delay"].max()) if len(detected) else None,
    )
    return summary, per_run
