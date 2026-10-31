"""
Stage 5 - Streamlit dashboard (decision support only - never controls equipment).
Run:  streamlit run app.py
"""
import os
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # make `src` importable
from src.ml_models import load_bundle
from src.optimizer import assess_run, early_warning_report, recommendations

st.set_page_config(page_title="AI Industrial Maintenance", page_icon="🏭", layout="wide")

# ── Theme colours ──
COLORS = {"NORMAL": "#2e9e5b", "WARNING": "#e0a100", "CRITICAL": "#d64545"}

# ── Custom CSS for a polished look ──
st.markdown("""
<style>
/* Remove default top padding */
.block-container { padding-top: 1rem; }

/* Status badge */
.status-badge {
    display: inline-block;
    padding: 6px 18px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 1.1rem;
    color: #fff;
}
.status-NORMAL   { background: #2e9e5b; }
.status-WARNING  { background: #e0a100; }
.status-CRITICAL { background: #d64545; }

/* KPI cards */
.kpi-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
    border: 1px solid #e0e0e0;
}
.kpi-card .label { font-size: 0.82rem; color: #666; margin-bottom: 4px; }
.kpi-card .value { font-size: 1.5rem; font-weight: 700; color: #222; }
.kpi-card .delta { font-size: 0.78rem; }
.delta-good  { color: #2e9e5b; }
.delta-bad   { color: #d64545; }

/* Sidebar tweaks */
section[data-testid="stSidebar"] > div { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_bundle():
    return load_bundle()


@st.cache_data
def get_assessment(_bundle, run_id, warn_t, crit_t):
    run = _bundle["test"][_bundle["test"]["run_id"] == run_id].sort_values("sample").reset_index(drop=True)
    return run, assess_run(_bundle, run, warn_t, crit_t)


@st.cache_data
def get_early_warning(_bundle, warn_t, crit_t):
    return early_warning_report(_bundle, warn_t, crit_t)


bundle = get_bundle()

# ── Header ──
st.markdown("# 🏭 AI-Based Industrial Maintenance & Process Optimization")
st.caption("Decision-support prototype for human review. It does not control any plant equipment.")

if bundle is None:
    st.error("No trained model found. Run `python src/train_model.py` first.")
    st.stop()

# ════════════════════════════════════════════════════════════════════
# Sidebar: choose the (replayed) live stream
# ════════════════════════════════════════════════════════════════════
test = bundle["test"]
st.sidebar.header("🔧 Plant Data Stream")
st.sidebar.caption(f"Data source: **{bundle['source']}**")
run_id = st.sidebar.selectbox("Simulation run (held-out test set)", sorted(test["run_id"].unique()))
st.sidebar.divider()
warn_t = st.sidebar.slider("Warning threshold (risk score)", 0.10, 0.90, 0.70, 0.05,
                           help="Alarm raised when the risk score crosses this value. 0.70 keeps alarms "
                                "under ~5 % of healthy operation.")
crit_t = st.sidebar.slider("Critical threshold (risk score)", 0.20, 1.00, 0.85, 0.05)
if crit_t <= warn_t:
    st.sidebar.warning("Critical threshold should be higher than the warning threshold.")
run, assessed = get_assessment(bundle, run_id, warn_t, crit_t)
n = len(run)
sensors = st.sidebar.multiselect("Telemetry to plot", bundle["sensors"], default=bundle["sensors"][:4])
st.sidebar.divider()
play = st.sidebar.checkbox("▶ Auto-play (simulate live feed)")
speed = st.sidebar.slider("Samples per refresh", 1, 10, 3)

if st.session_state.get("run") != run_id:                 # new run -> restart the clock
    st.session_state.run, st.session_state.t = run_id, 0
if play:                                                   # advance before the slider is created
    st.session_state.t = min(st.session_state.get("t", 0) + speed, n - 1)
t = st.sidebar.slider("Current time step", 0, n - 1, key="t")

cur = assessed.iloc[t]
status = cur["status"]
history = assessed.iloc[: t + 1]

# ════════════════════════════════════════════════════════════════════
# Tabs
# ════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Live Overview",
    "📈 Telemetry",
    "⚠️ Failure Predictions & Alerts",
    "🛠️ Decision Support",
])

# ─── Tab 1: Live Overview ─────────────────────────────────────────
with tab1:
    # KPI row using custom HTML for a cleaner look
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="kpi-card">'
            f'  <div class="label">Plant Status</div>'
            f'  <span class="status-badge status-{status}">{status}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="kpi-card">'
            f'  <div class="label">Equipment Health Index</div>'
            f'  <div class="value">{cur["health_index"]:.0f} / 100</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    risk_delta = cur["risk"] - assessed["risk"].iloc[max(0, t - 5)]
    delta_cls = "delta-good" if risk_delta <= 0 else "delta-bad"
    with c3:
        st.markdown(
            f'<div class="kpi-card">'
            f'  <div class="label">Risk Score</div>'
            f'  <div class="value">{cur["risk"]:.2f}</div>'
            f'  <div class="delta {delta_cls}">{risk_delta:+.2f} vs 5 samples ago</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="kpi-card">'
            f'  <div class="label">Failure Probability</div>'
            f'  <div class="value">{cur["p_fail"]:.0%}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")  # spacer

    # Risk trend chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history["sample"], y=history["risk"], mode="lines",
        name="Risk", line=dict(color="#3366cc", width=2.5),
        fill="tozeroy", fillcolor="rgba(51, 102, 204, 0.08)",
    ))
    fig.add_hline(y=warn_t, line_dash="dash", line_color=COLORS["WARNING"],
                  annotation_text=f"WARNING {warn_t:.2f}", annotation_position="top left")
    fig.add_hline(y=crit_t, line_dash="dash", line_color=COLORS["CRITICAL"],
                  annotation_text=f"CRITICAL {crit_t:.2f}", annotation_position="top left")
    fig.update_layout(
        height=340,
        yaxis=dict(range=[0, 1], title="Risk Score", gridcolor="#eee"),
        xaxis=dict(range=[0, n], title="Sample", gridcolor="#eee"),
        margin=dict(t=20, b=30, l=50, r=20),
        plot_bgcolor="#fafbfc",
    )
    st.plotly_chart(fig, width="stretch")

# ─── Tab 2: Telemetry ─────────────────────────────────────────────
with tab2:
    if not sensors:
        st.info("Select at least one variable in the sidebar.")
    for s in sensors:
        d = run.iloc[: t + 1]
        normal_val = float(bundle["normal_mean"][s])
        normal_std = float(bundle["normal_std"][s])

        f = go.Figure()
        # Normal band (±2σ)
        f.add_hrect(
            y0=normal_val - 2 * normal_std, y1=normal_val + 2 * normal_std,
            fillcolor="rgba(46, 158, 91, 0.07)", line_width=0,
            annotation_text="normal ±2σ", annotation_position="top left",
        )
        f.add_trace(go.Scatter(
            x=d["sample"], y=d[s], mode="lines", name=s,
            line=dict(width=2),
        ))
        f.add_hline(y=normal_val, line_dash="dot", line_color="#888",
                     annotation_text="normal mean")
        f.update_layout(
            height=230, title=dict(text=s, font=dict(size=13)),
            xaxis=dict(range=[0, n], gridcolor="#eee"),
            yaxis=dict(gridcolor="#eee"),
            margin=dict(t=40, b=10, l=50, r=20),
            plot_bgcolor="#fafbfc",
        )
        st.plotly_chart(f, width="stretch")

# ─── Tab 3: Failure Predictions & Alerts ──────────────────────────
with tab3:
    st.subheader("Detected Anomalies / Alerts So Far")
    alerts = history[history["status"] != "NORMAL"][["sample", "status", "risk", "p_fail", "anomaly"]]
    if alerts.empty:
        st.success("✅ No alerts raised in this run so far.")
    else:
        first = alerts.iloc[0]
        st.warning(f"First alert at sample **{int(first['sample'])}** ({first['status']}).")
        st.dataframe(alerts.round(3).tail(50), width="stretch", hide_index=True)

    st.divider()
    st.subheader("Model Evaluation (held-out 20 % test runs)")
    m = pd.DataFrame(bundle["metrics"]).T[["precision", "recall", "f1", "tp", "fp", "fn", "tn"]]
    st.dataframe(m.round(3), width="stretch")
    st.caption(
        f"Classifier in use: **{bundle['classifier_name']}** (best F1). "
        "Isolation Forest provides the unsupervised anomaly score."
    )

    st.divider()
    st.subheader("Early-Warning Performance")
    st.caption("How quickly the system raises its first alarm after each fault is injected into a run. "
               "Move the threshold sliders in the sidebar to trade detection against false alarms.")
    summary, per_run = get_early_warning(bundle, warn_t, crit_t)
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Faulty runs detected", f"{summary['detected']} / {summary['faulty_runs']}")
    e2.metric("Missed faults", summary["missed"])
    med = summary["median_delay_samples"]
    e3.metric("Median detection delay",
              "—" if med is None else f"{med:.0f} samples ({summary['median_delay_minutes']:.0f} min)")
    e4.metric("False alarms", f"{summary['normal_false_alarms']} on normal + {summary['pre_onset_false_alarms']} pre-onset")
    with st.expander("Per-run detection detail"):
        st.dataframe(per_run, width="stretch", hide_index=True)

    st.divider()
    st.subheader("Which Sensors Drive the Prediction (Feature Importance)")
    imp = bundle.get("importances")
    if imp is None:
        st.info("No feature importance available for this model type.")
    else:
        top = imp.head(15)[::-1]                      # smallest at top for a horizontal bar chart
        fig_imp = go.Figure(go.Bar(
            x=top.values, y=[str(i) for i in top.index], orientation="h",
            marker_color="#3366cc",
        ))
        fig_imp.update_layout(
            height=460, margin=dict(t=20, b=30, l=200, r=20),
            xaxis=dict(title="Importance", gridcolor="#eee"),
            plot_bgcolor="#fafbfc",
        )
        st.plotly_chart(fig_imp, width="stretch")
        st.caption("Higher = the model relies on this sensor more when deciding whether a fault is present.")

# ─── Tab 4: Decision Support ──────────────────────────────────────
with tab4:
    rec = recommendations(bundle, run, assessed, t)
    st.subheader("Maintenance Recommendations (for engineer review)")
    box = {"NORMAL": st.success, "WARNING": st.warning, "CRITICAL": st.error}[status]
    box(rec["timing"])
    st.markdown("**Variables deviating most from normal behaviour → likely equipment:**")
    st.dataframe(rec["items"], width="stretch", hide_index=True)
    st.caption("Recommendations are advisory. Any action must be approved and executed by qualified plant personnel.")

# ── Auto-play rerun ──
if play and t < n - 1:
    time.sleep(0.4)
    st.rerun()
