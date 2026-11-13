"""
Stage 5 - Streamlit dashboard (decision support only - never controls equipment).
Run:  streamlit run app.py
"""
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.ml_models import load_bundle
from src.optimizer import assess_run, early_warning_report, recommendations

st.set_page_config(
    page_title="AI Industrial Maintenance",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Palette ──────────────────────────────────────────────────────────
C = {
    "NORMAL":  "#00d26a", "WARNING": "#ffb300", "CRITICAL": "#ff4d4d",
    "BLUE":    "#4f8ef7", "PURPLE":  "#a855f7", "CYAN":     "#06b6d4",
    "BG":      "#080c14", "CARD":    "#0f1623", "CARD2":    "#111827",
    "BORDER":  "#1e2d45", "BORDER2": "#243352",
    "TEXT":    "#dde6f5", "MUTED":   "#7a8ca6", "FAINT":    "#3a4a62",
}
SENSOR_PALETTE = ["#4f8ef7","#00d26a","#ffb300","#a855f7",
                  "#06b6d4","#f97316","#ec4899","#84cc16"]

# ════════════════════════════════════════════════════════════════════
# CSS
# ════════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── BASE ── */
html, body, [class*="css"] {{ font-family:'Inter',sans-serif; }}

.stApp {{
    background: radial-gradient(ellipse at top left, #0a1020 0%, {C['BG']} 55%, #05080f 100%);
    color:{C['TEXT']};
}}
.block-container {{
    padding: 1rem 1rem 2rem 1rem !important;
    max-width:100% !important;
}}

/* ── HERO ── */
.hero {{
    background: linear-gradient(120deg,#07101e 0%,#0d1e3c 40%,#091730 70%,#070e1c 100%);
    border:1px solid {C['BORDER2']};
    border-radius:0 0 18px 18px;
    padding:22px 36px;
    margin-bottom:18px;
    margin-left:-1rem;
    margin-right:-1rem;
    display:flex; align-items:center; justify-content:space-between;
    position:relative; overflow:hidden;
    box-shadow:0 10px 40px rgba(79,142,247,0.14), 0 2px 8px rgba(0,0,0,0.6);
}}
.hero::before {{
    content:'';
    position:absolute; top:-40%; right:-5%;
    width:500px; height:500px;
    background:radial-gradient(circle,rgba(79,142,247,0.09) 0%,transparent 65%);
    pointer-events:none;
}}
.hero::after {{
    content:'';
    position:absolute; bottom:-30%; left:30%;
    width:300px; height:300px;
    background:radial-gradient(circle,rgba(168,85,247,0.05) 0%,transparent 70%);
    pointer-events:none;
}}
.hero-title {{
    font-size:1.8rem; font-weight:800; color:{C['TEXT']};
    margin:0; letter-spacing:-0.6px; line-height:1.2;
}}
.hero-title em {{ font-style:normal; color:{C['BLUE']}; }}
.hero-sub {{
    font-size:0.8rem; color:{C['MUTED']}; margin-top:6px;
    display:flex; align-items:center; gap:10px;
}}
.hero-pill {{
    display:inline-flex; align-items:center; gap:5px;
    background:rgba(79,142,247,0.12); border:1px solid rgba(79,142,247,0.28);
    border-radius:20px; padding:3px 12px;
    font-size:0.72rem; color:{C['BLUE']}; font-weight:600;
    letter-spacing:0.6px; text-transform:uppercase;
}}
.hero-time {{
    font-size:0.75rem; color:{C['FAINT']};
    font-family:'JetBrains Mono',monospace;
    text-align:right;
}}

/* ── ALERT BANNER ── */
.alert-banner {{
    border-radius:12px; padding:12px 20px; margin-bottom:16px;
    display:flex; align-items:center; gap:12px;
    font-weight:600; font-size:0.9rem;
}}
.alert-banner.WARNING {{
    background:rgba(255,179,0,0.1); border:1px solid rgba(255,179,0,0.35);
    color:{C['WARNING']};
}}
.alert-banner.CRITICAL {{
    background:rgba(255,77,77,0.12); border:1px solid rgba(255,77,77,0.4);
    color:{C['CRITICAL']};
    box-shadow:0 0 20px rgba(255,77,77,0.08);
    animation: criticalPulse 2s infinite;
}}
@keyframes criticalPulse {{
    0%,100% {{ box-shadow:0 0 20px rgba(255,77,77,0.08); }}
    50%      {{ box-shadow:0 0 30px rgba(255,77,77,0.18); }}
}}

/* ── KPI CARDS ── */
.kpi-row {{
    display:grid; grid-template-columns:repeat(4,1fr);
    gap:14px; margin-bottom:16px;
}}
.kpi {{
    background:linear-gradient(160deg,{C['CARD']},{C['CARD2']});
    border:1px solid {C['BORDER']};
    border-radius:16px; padding:20px 22px 16px;
    position:relative; overflow:hidden;
    box-shadow:0 4px 20px rgba(0,0,0,0.3);
}}
.kpi-bar {{
    position:absolute; top:0; left:0; right:0;
    height:3px; border-radius:16px 16px 0 0;
}}
.kpi-bg-icon {{
    position:absolute; bottom:-10px; right:10px;
    font-size:4rem; opacity:0.04; user-select:none; pointer-events:none;
}}
.kpi-label {{
    font-size:0.7rem; color:{C['MUTED']}; text-transform:uppercase;
    letter-spacing:0.9px; font-weight:600; margin-bottom:10px;
}}
.kpi-value {{
    font-size:2.1rem; font-weight:800; color:{C['TEXT']}; line-height:1;
    font-family:'JetBrains Mono',monospace; margin-bottom:8px;
}}
.kpi-sub {{ font-size:0.72rem; color:{C['MUTED']}; }}
.kpi-delta {{ font-size:0.72rem; font-weight:600; margin-top:4px; }}

/* Progress bar */
.prog-wrap {{
    background:{C['FAINT']}; border-radius:4px; height:5px;
    margin-top:10px; overflow:hidden;
}}
.prog-fill {{
    height:100%; border-radius:4px;
    transition:width 0.5s ease;
}}

/* Status dot + badge */
.status-badge {{
    display:inline-flex; align-items:center; gap:7px;
    padding:7px 18px; border-radius:24px;
    font-weight:700; font-size:1rem; letter-spacing:0.4px;
    margin-top:4px;
}}
.dot {{
    width:9px; height:9px; border-radius:50%;
    animation:blink 1.6s ease-in-out infinite;
}}
.sN {{ background:rgba(0,210,106,0.15); border:1px solid {C['NORMAL']}; color:{C['NORMAL']}; }}
.sW {{ background:rgba(255,179,0,0.14); border:1px solid {C['WARNING']}; color:{C['WARNING']}; }}
.sC {{ background:rgba(255,77,77,0.14); border:1px solid {C['CRITICAL']}; color:{C['CRITICAL']}; }}
@keyframes blink {{
    0%,100% {{ opacity:1; transform:scale(1); }}
    50%      {{ opacity:0.5; transform:scale(0.8); }}
}}

/* ── SENSOR GRID ── */
.sensor-grid {{
    display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr));
    gap:10px; margin-top:4px;
}}
.sensor-tile {{
    background:{C['CARD']}; border:1px solid {C['BORDER']};
    border-radius:12px; padding:12px 14px;
    text-align:center; position:relative; overflow:hidden;
}}
.sensor-tile .s-name {{
    font-size:0.68rem; color:{C['MUTED']}; font-weight:500;
    text-transform:uppercase; letter-spacing:0.6px; margin-bottom:4px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}}
.sensor-tile .s-val {{
    font-size:1.1rem; font-weight:700; font-family:'JetBrains Mono',monospace;
    color:{C['TEXT']};
}}
.sensor-tile .s-dev {{
    font-size:0.65rem; margin-top:3px;
}}
.sensor-tile-bar {{
    position:absolute; bottom:0; left:0; right:0; height:2px;
}}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {{
    background:{C['CARD']} !important;
    border-radius:14px !important; padding:5px !important;
    gap:3px !important; border:1px solid {C['BORDER']} !important;
}}
.stTabs [data-baseweb="tab"] {{
    background:transparent !important; color:{C['MUTED']} !important;
    border-radius:10px !important; padding:9px 22px !important;
    font-weight:500 !important; font-size:0.88rem !important;
    transition:all 0.2s !important; border:none !important;
}}
.stTabs [aria-selected="true"] {{
    background:linear-gradient(135deg,#162445,#122040) !important;
    color:{C['BLUE']} !important;
    box-shadow:0 2px 10px rgba(79,142,247,0.22) !important;
    font-weight:600 !important;
}}
.stTabs [data-baseweb="tab-panel"] {{ padding-top:18px !important; padding-left:1rem !important; padding-right:1rem !important; }}

/* ── SECTION HEADERS ── */
.sh {{
    display:flex; align-items:center; gap:10px;
    font-size:1rem; font-weight:700; color:{C['TEXT']};
    margin:14px 0 10px; padding-bottom:9px;
    border-bottom:1px solid {C['BORDER']};
}}
.sh-icon {{
    width:30px; height:30px;
    background:linear-gradient(135deg,#162445,#1e3366);
    border:1px solid {C['BORDER']};
    border-radius:8px; display:flex;
    align-items:center; justify-content:center;
    font-size:0.9rem;
}}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {{
    background:linear-gradient(185deg,#060c18 0%,#040810 100%) !important;
    border-right:1px solid {C['BORDER']} !important;
}}
section[data-testid="stSidebar"] > div {{
    padding:0.8rem 1rem !important;
}}
.sb-logo {{
    text-align:center; padding:14px 0 18px;
    border-bottom:1px solid {C['BORDER']}; margin-bottom:14px;
}}
.sb-logo-icon {{ font-size:2rem; line-height:1; }}
.sb-logo-name {{
    font-size:1rem; font-weight:800; color:{C['BLUE']};
    letter-spacing:-0.3px; margin-top:4px;
}}
.sb-logo-ver {{
    font-size:0.65rem; color:{C['FAINT']};
    text-transform:uppercase; letter-spacing:1.2px;
}}
.sb-section {{
    font-size:0.68rem; font-weight:700; color:{C['FAINT']};
    text-transform:uppercase; letter-spacing:1.2px;
    margin:14px 0 6px;
}}
.run-info {{
    background:{C['CARD']}; border:1px solid {C['BORDER']};
    border-radius:10px; padding:10px 14px; margin-bottom:4px;
}}
.run-info-row {{
    display:flex; justify-content:space-between; align-items:center;
    font-size:0.75rem; padding:3px 0;
}}
.run-info-label {{ color:{C['MUTED']}; }}
.run-info-val {{ color:{C['TEXT']}; font-weight:600; font-family:'JetBrains Mono',monospace; }}

/* ── METRIC CARDS ── */
[data-testid="stMetric"] {{
    background:linear-gradient(160deg,{C['CARD']},{C['CARD2']}) !important;
    border:1px solid {C['BORDER']} !important;
    border-radius:14px !important; padding:16px !important;
}}
[data-testid="stMetricLabel"] {{
    color:{C['MUTED']} !important; font-size:0.72rem !important;
    text-transform:uppercase; letter-spacing:0.7px;
}}
[data-testid="stMetricValue"] {{
    color:{C['TEXT']} !important;
    font-family:'JetBrains Mono',monospace !important;
    font-size:1.4rem !important;
}}

/* ── DATAFRAME ── */
.stDataFrame {{ border-radius:12px !important; overflow:hidden !important; border:1px solid {C['BORDER']} !important; }}

/* ── ALERTS ── */
.stAlert {{ border-radius:12px !important; border-left-width:4px !important; }}

/* ── FOOTER ── */
.footer {{
    margin-top:40px; padding:16px 20px;
    background:{C['CARD']}; border:1px solid {C['BORDER']};
    border-radius:12px; display:flex; align-items:center;
    justify-content:space-between;
    font-size:0.72rem; color:{C['FAINT']};
}}
.footer strong {{ color:{C['MUTED']}; }}

/* ── MISC ── */
hr {{ border-color:{C['BORDER']} !important; margin:1.4rem 0 !important; }}
.stCheckbox label {{ color:{C['TEXT']} !important; }}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] .stMultiSelect label {{
    color:{C['MUTED']} !important; font-size:0.75rem !important;
    font-weight:600 !important; text-transform:uppercase !important;
    letter-spacing:0.7px !important;
}}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════
def dark_layout(h=320, t=16, b=36, l=55, r=20):
    return dict(
        height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=C["CARD"],
        font=dict(color=C["MUTED"], family="Inter"),
        margin=dict(t=t, b=b, l=l, r=r),
        xaxis=dict(gridcolor=C["BORDER"], zeroline=False, tickfont=dict(color=C["FAINT"])),
        yaxis=dict(gridcolor=C["BORDER"], zeroline=False, tickfont=dict(color=C["FAINT"])),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C["MUTED"])),
        hovermode="x unified",
    )


def gauge_fig(value, title, max_val=1.0, suffix="", height=220, invert=False):
    pct = value / max_val
    if invert:
        bar_color = C["NORMAL"] if pct > 0.6 else (C["WARNING"] if pct > 0.35 else C["CRITICAL"])
        steps = [
            dict(range=[0,              max_val*0.35], color="rgba(255,77,77,0.08)"),
            dict(range=[max_val*0.35,   max_val*0.6],  color="rgba(255,179,0,0.06)"),
            dict(range=[max_val*0.6,    max_val],       color="rgba(0,210,106,0.06)"),
        ]
        threshold_val = max_val * 0.35
    else:
        bar_color = C["NORMAL"] if pct < 0.5 else (C["WARNING"] if pct < 0.75 else C["CRITICAL"])
        steps = [
            dict(range=[0,              max_val*0.5],  color="rgba(0,210,106,0.06)"),
            dict(range=[max_val*0.5,    max_val*0.75], color="rgba(255,179,0,0.06)"),
            dict(range=[max_val*0.75,   max_val],      color="rgba(255,77,77,0.08)"),
        ]
        threshold_val = max_val * 0.85

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(font=dict(size=28, family="JetBrains Mono", color=C["TEXT"]), suffix=suffix),
        title=dict(text=title, font=dict(size=11, color=C["MUTED"], family="Inter")),
        gauge=dict(
            axis=dict(range=[0, max_val], tickcolor=C["FAINT"],
                      tickfont=dict(color=C["FAINT"], size=9)),
            bar=dict(color=bar_color, thickness=0.6),
            bgcolor=C["BORDER"], borderwidth=0,
            steps=steps,
            threshold=dict(line=dict(color=C["CRITICAL"], width=2),
                           thickness=0.75, value=threshold_val),
        ),
    ))
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter"),
        margin=dict(t=30, b=10, l=20, r=20),
    )
    return fig


def sh(icon, text):
    st.markdown(
        f'<div class="sh"><div class="sh-icon">{icon}</div>{text}</div>',
        unsafe_allow_html=True,
    )


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

# ════════════════════════════════════════════════════════════════════
# HERO HEADER
# ════════════════════════════════════════════════════════════════════
now_str = datetime.now().strftime("%d %b %Y  %H:%M:%S")
st.markdown(f"""
<div class="hero">
  <div>
    <div class="hero-title">🏭 AI-Based <em>Industrial Maintenance</em> &amp; Process Optimization</div>
    <div class="hero-sub">
      <span class="hero-pill">🔒 Advisory Mode</span>
      <span>Predictive maintenance · Anomaly detection · Decision support</span>
    </div>
  </div>
  <div>
    <div class="hero-time">🕐 {now_str}</div>
    <div style="margin-top:6px;text-align:right;">
      <span class="hero-pill">v2.0</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if bundle is None:
    st.error("⚠️ No trained model found. Run `python src/train_model.py` first.")
    st.stop()

# ════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════
test = bundle["test"]

with st.sidebar:
    st.markdown(f"""
    <div class="sb-logo">
      <div class="sb-logo-icon">⚙️</div>
      <div class="sb-logo-name">Control Panel</div>
      <div class="sb-logo-ver">AI Maintenance System</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sb-section">📡 Data Source</div>', unsafe_allow_html=True)
    st.caption(f"`{bundle['source']}`")
    run_id = st.selectbox("Simulation Run", sorted(test["run_id"].unique()), label_visibility="collapsed")

    st.markdown('<div class="sb-section">🎚 Alarm Thresholds</div>', unsafe_allow_html=True)
    warn_t = st.slider("Warning threshold ⚠️", 0.10, 0.90, 0.70, 0.05,
                       help="Alarm fires when risk score crosses this value.")
    crit_t = st.slider("Critical threshold 🔴", 0.20, 1.00, 0.85, 0.05)
    if crit_t <= warn_t:
        st.warning("Critical must be > Warning threshold.")

    st.markdown('<div class="sb-section">📊 Telemetry Channels</div>', unsafe_allow_html=True)
    sensors = st.multiselect("Sensors", bundle["sensors"],
                             default=bundle["sensors"][:4], label_visibility="collapsed")

    st.markdown('<div class="sb-section">▶ Playback</div>', unsafe_allow_html=True)
    play  = st.checkbox("Auto-play live feed")
    speed = st.slider("Samples / refresh", 1, 10, 3)

run, assessed = get_assessment(bundle, run_id, warn_t, crit_t)
n = len(run)

if st.session_state.get("run") != run_id:
    st.session_state.run, st.session_state.t = run_id, 0
if play:
    st.session_state.t = min(st.session_state.get("t", 0) + speed, n - 1)
t = st.sidebar.slider("⏱ Time step", 0, n - 1, key="t")

cur     = assessed.iloc[t]
status  = cur["status"]
history = assessed.iloc[:t + 1]

n_warn = int((history["status"] == "WARNING").sum())
n_crit = int((history["status"] == "CRITICAL").sum())

st.sidebar.markdown('<div class="sb-section">📋 Run Summary</div>', unsafe_allow_html=True)
st.sidebar.markdown(f"""
<div class="run-info">
  <div class="run-info-row">
    <span class="run-info-label">Run ID</span>
    <span class="run-info-val">{run_id}</span>
  </div>
  <div class="run-info-row">
    <span class="run-info-label">Progress</span>
    <span class="run-info-val">{t+1} / {n}</span>
  </div>
  <div class="run-info-row">
    <span class="run-info-label">⚠ Warnings</span>
    <span class="run-info-val" style="color:{C['WARNING']}">{n_warn}</span>
  </div>
  <div class="run-info-row">
    <span class="run-info-label">🔴 Criticals</span>
    <span class="run-info-val" style="color:{C['CRITICAL']}">{n_crit}</span>
  </div>
  <div class="run-info-row">
    <span class="run-info-label">Model</span>
    <span class="run-info-val">{bundle['classifier_name'][:14]}</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# ALERT BANNER
# ════════════════════════════════════════════════════════════════════
if status != "NORMAL":
    icon = "⚠️" if status == "WARNING" else "🚨"
    msg  = (f"Plant in <strong>{status}</strong> state — "
            f"Risk score <strong>{cur['risk']:.2f}</strong>, "
            f"failure probability <strong>{cur['p_fail']:.0%}</strong>. "
            f"Engineer review required.")
    st.markdown(f'<div class="alert-banner {status}">{icon}&nbsp; {msg}</div>',
                unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📊  Live Overview",
    "📈  Telemetry",
    "⚠️  Predictions & Alerts",
    "🛠️  Decision Support",
])

# ──────────────────────────────────────────────────────────────────
# TAB 1 — Live Overview
# ──────────────────────────────────────────────────────────────────
with tab1:
    risk_delta  = cur["risk"] - assessed["risk"].iloc[max(0, t - 5)]
    health      = float(cur["health_index"])
    pfail       = float(cur["p_fail"])

    sa = {"NORMAL": "00d26a", "WARNING": "ffb300", "CRITICAL": "ff4d4d"}.get(status, "4f8ef7")
    ha = "00d26a" if health >= 70 else ("ffb300" if health >= 40 else "ff4d4d")
    pa = "ff4d4d" if pfail > 0.5 else "00d26a"
    delta_arrow = "▲" if risk_delta > 0 else "▼"
    delta_color = "#ff4d4d" if risk_delta > 0 else "#00d26a"

    st.markdown(f"""
    <div class="kpi-row">

      <div class="kpi">
        <div class="kpi-bar" style="background:linear-gradient(90deg,#{sa},#{sa}88);"></div>
        <div class="kpi-bg-icon">🏭</div>
        <div class="kpi-label">Plant Status</div>
        <div class="status-badge s{status[0]}">
          <span class="dot" style="background:#{sa};"></span>
          {status}
        </div>
        <div class="kpi-sub" style="margin-top:8px;">
          ⚠ {n_warn} warnings &nbsp;·&nbsp; 🔴 {n_crit} criticals
        </div>
      </div>

      <div class="kpi">
        <div class="kpi-bar" style="background:linear-gradient(90deg,#{ha},#{ha}88);"></div>
        <div class="kpi-bg-icon">💚</div>
        <div class="kpi-label">Equipment Health Index</div>
        <div class="kpi-value">{health:.0f}<span style="font-size:1rem;color:{C['MUTED']};font-family:Inter;"> / 100</span></div>
        <div class="prog-wrap">
          <div class="prog-fill" style="width:{health:.0f}%;background:linear-gradient(90deg,#{ha},#{ha}bb);"></div>
        </div>
      </div>

      <div class="kpi">
        <div class="kpi-bar" style="background:linear-gradient(90deg,{C['BLUE']},{C['BLUE']}88);"></div>
        <div class="kpi-bg-icon">📉</div>
        <div class="kpi-label">Risk Score</div>
        <div class="kpi-value">{cur['risk']:.3f}</div>
        <div class="kpi-delta" style="color:{delta_color};">
          {delta_arrow} {abs(risk_delta):.3f} vs 5 steps ago
        </div>
        <div class="prog-wrap">
          <div class="prog-fill" style="width:{cur['risk']*100:.0f}%;background:linear-gradient(90deg,{C['BLUE']},{C['BLUE']}bb);"></div>
        </div>
      </div>

      <div class="kpi">
        <div class="kpi-bar" style="background:linear-gradient(90deg,#{pa},#{pa}88);"></div>
        <div class="kpi-bg-icon">⚡</div>
        <div class="kpi-label">Failure Probability</div>
        <div class="kpi-value">{pfail:.1%}</div>
        <div class="prog-wrap">
          <div class="prog-fill" style="width:{pfail*100:.0f}%;background:linear-gradient(90deg,#{pa},#{pa}bb);"></div>
        </div>
        <div class="kpi-sub" style="margin-top:4px;">
          Anomaly: {'Yes 🔴' if cur['anomaly'] else 'No ✅'}
        </div>
      </div>

    </div>
    """, unsafe_allow_html=True)

    # ── Gauge row + Risk trend ──────────────────────────────────────
    g1, g2, chart_col = st.columns([1, 1, 3])

    with g1:
        st.plotly_chart(gauge_fig(cur["risk"], "Risk Score", max_val=1.0, height=220, invert=False),
                        width="stretch")
    with g2:
        st.plotly_chart(gauge_fig(health, "Health Index", max_val=100, height=220, invert=True),
                        width="stretch")
    with chart_col:
        fig = go.Figure()
        fig.add_hrect(y0=0,      y1=warn_t, fillcolor="rgba(0,210,106,0.04)",  line_width=0)
        fig.add_hrect(y0=warn_t, y1=crit_t, fillcolor="rgba(255,179,0,0.05)",  line_width=0)
        fig.add_hrect(y0=crit_t, y1=1,      fillcolor="rgba(255,77,77,0.06)",  line_width=0)
        fig.add_trace(go.Scatter(
            x=history["sample"], y=history["risk"],
            mode="lines", name="Risk Score",
            line=dict(color=C["BLUE"], width=2.5),
            fill="tozeroy", fillcolor="rgba(79,142,247,0.07)",
            hovertemplate="Sample %{x}<br>Risk: <b>%{y:.3f}</b><extra></extra>",
        ))
        for s_name, col in [("WARNING", C["WARNING"]), ("CRITICAL", C["CRITICAL"])]:
            pts = history[history["status"] == s_name]
            if not pts.empty:
                fig.add_trace(go.Scatter(
                    x=pts["sample"], y=pts["risk"], mode="markers",
                    name=s_name.capitalize(),
                    marker=dict(color=col, size=6),
                    hovertemplate=f"{s_name} @ %{{x}}<extra></extra>",
                ))
        fig.add_hline(y=warn_t, line_dash="dash", line_color=C["WARNING"], line_width=1.5,
                      annotation_text=f"⚠ {warn_t:.2f}",
                      annotation_font=dict(color=C["WARNING"], size=10),
                      annotation_position="top left")
        fig.add_hline(y=crit_t, line_dash="dash", line_color=C["CRITICAL"], line_width=1.5,
                      annotation_text=f"🔴 {crit_t:.2f}",
                      annotation_font=dict(color=C["CRITICAL"], size=10),
                      annotation_position="top left")
        layout = dark_layout(h=220, t=12, b=36)
        layout["yaxis"]["range"]  = [0, 1]
        layout["yaxis"]["title"]  = "Risk Score"
        layout["xaxis"]["range"]  = [0, n]
        layout["xaxis"]["title"]  = "Sample"
        layout["title"] = dict(text="<b>Risk Score Timeline</b>",
                               font=dict(size=12, color=C["MUTED"]), x=0.01)
        fig.update_layout(**layout)
        st.plotly_chart(fig, width="stretch")

    # ── Sensor Status Grid ──────────────────────────────────────────
    sh("📡", "Live Sensor Readings")
    tiles_html = '<div class="sensor-grid">'
    for idx, s in enumerate(bundle["sensors"]):
        val       = float(run.iloc[t][s])
        mu        = float(bundle["normal_mean"][s])
        sig       = float(bundle["normal_std"][s])
        dev       = (val - mu) / (sig + 1e-9)
        color     = SENSOR_PALETTE[idx % len(SENSOR_PALETTE)]
        dev_color = C["NORMAL"] if abs(dev) < 1 else (C["WARNING"] if abs(dev) < 2 else C["CRITICAL"])
        tiles_html += f"""
        <div class="sensor-tile">
          <div class="sensor-tile-bar" style="background:{color};"></div>
          <div class="s-name">{s}</div>
          <div class="s-val">{val:.2f}</div>
          <div class="s-dev" style="color:{dev_color};">{dev:+.1f}σ</div>
        </div>"""
    tiles_html += "</div>"
    st.markdown(tiles_html, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# TAB 2 — Telemetry
# ──────────────────────────────────────────────────────────────────
with tab2:
    if not sensors:
        st.info("Select at least one sensor in the sidebar.")
    else:
        d = run.iloc[: t + 1]
        pairs = [sensors[i:i+2] for i in range(0, len(sensors), 2)]
        for pair in pairs:
            cols = st.columns(len(pair))
            for col, s in zip(cols, pair):
                idx        = bundle["sensors"].index(s)
                color      = SENSOR_PALETTE[idx % len(SENSOR_PALETTE)]
                normal_val = float(bundle["normal_mean"][s])
                normal_std = float(bundle["normal_std"][s])
                with col:
                    f = go.Figure()
                    f.add_hrect(
                        y0=normal_val - 2 * normal_std,
                        y1=normal_val + 2 * normal_std,
                        fillcolor="rgba(0,210,106,0.05)", line_width=0,
                        annotation_text="±2σ",
                        annotation_font=dict(color="#00d26a44", size=9),
                        annotation_position="top right",
                    )
                    f.add_hline(y=normal_val, line_dash="dot",
                                line_color=C["FAINT"], line_width=1)
                    f.add_trace(go.Scatter(
                        x=d["sample"], y=d[s],
                        mode="lines", name=s,
                        line=dict(color=color, width=2),
                        fill="tozeroy", fillcolor=f"{color}18",
                        hovertemplate=f"<b>{s}</b><br>%{{y:.3f}}<extra></extra>",
                    ))
                    layout = dark_layout(h=240, t=42, b=16)
                    layout["title"] = dict(
                        text=f"<b>{s}</b>",
                        font=dict(size=12, color=C["TEXT"], family="Inter"), x=0.01,
                    )
                    layout["xaxis"]["range"]  = [0, n]
                    layout["xaxis"]["title"] = "Sample"
                    layout["showlegend"] = False
                    f.update_layout(**layout)
                    st.plotly_chart(f, width="stretch")

# ──────────────────────────────────────────────────────────────────
# TAB 3 — Predictions & Alerts
# ──────────────────────────────────────────────────────────────────
with tab3:
    sh("🚨", "Detected Anomalies / Alerts So Far")
    alerts = history[history["status"] != "NORMAL"][["sample","status","risk","p_fail","anomaly"]]
    if alerts.empty:
        st.success("✅ No alerts raised in this run so far.")
    else:
        first = alerts.iloc[0]
        st.warning(f"⚠️ First alert at sample **{int(first['sample'])}** — Status: **{first['status']}**")
        st.dataframe(
            alerts.round(3).tail(50).style.map(
                lambda v: (f"color:{C['CRITICAL']};font-weight:700" if v == "CRITICAL"
                           else f"color:{C['WARNING']};font-weight:700" if v == "WARNING"
                           else ""),
                subset=["status"],
            ),
            width="stretch", hide_index=True,
        )

    if not alerts.empty:
        risk_hist = go.Figure(go.Histogram(
            x=alerts["risk"], nbinsx=20,
            marker=dict(color=C["CRITICAL"], opacity=0.7,
                        line=dict(color=C["BORDER"], width=0.5)),
        ))
        layout = dark_layout(h=180, t=12, b=30)
        layout["title"] = dict(text="<b>Alert Risk Score Distribution</b>",
                               font=dict(size=11, color=C["MUTED"]), x=0.01)
        layout["xaxis"]["title"] = "Risk Score"
        layout["yaxis"]["title"] = "Count"
        risk_hist.update_layout(**layout)
        st.plotly_chart(risk_hist, width="stretch")

    st.divider()
    sh("📉", "Model Evaluation (held-out 20% test runs)")
    m = pd.DataFrame(bundle["metrics"]).T[["precision","recall","f1","tp","fp","fn","tn"]]
    f1_fig = go.Figure(go.Bar(
        x=m.index, y=m["f1"],
        marker=dict(
            color=[C["NORMAL"] if v >= 0.8 else C["WARNING"] if v >= 0.6 else C["CRITICAL"]
                   for v in m["f1"]],
            line=dict(color=C["BORDER"], width=1),
        ),
        text=[f"{v:.2f}" for v in m["f1"]],
        textposition="outside",
        textfont=dict(color=C["MUTED"], size=10),
    ))
    layout = dark_layout(h=200, t=16, b=36)
    layout["yaxis"]["range"]  = [0, 1.1]
    layout["yaxis"]["title"]  = "F1 Score"
    layout["title"] = dict(text="<b>F1 Score by Class</b>",
                           font=dict(size=11, color=C["MUTED"]), x=0.01)
    f1_fig.update_layout(**layout)
    st.plotly_chart(f1_fig, width="stretch")
    st.dataframe(m.round(3), width="stretch")
    st.caption(f"🤖 Classifier: **{bundle['classifier_name']}** · Isolation Forest for anomaly scoring")

    st.divider()
    sh("⏱️", "Early-Warning Performance")
    summary, per_run = get_early_warning(bundle, warn_t, crit_t)
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Faulty Runs Detected", f"{summary['detected']} / {summary['faulty_runs']}")
    e2.metric("Missed Faults", summary["missed"])
    med = summary["median_delay_samples"]
    e3.metric("Median Detection Delay",
              "—" if med is None else f"{med:.0f} smp · {summary['median_delay_minutes']:.0f} min")
    e4.metric("False Alarms",
              f"{summary['normal_false_alarms']} norm + {summary['pre_onset_false_alarms']} pre")
    with st.expander("🔍 Per-run Detection Detail"):
        st.dataframe(per_run, width="stretch", hide_index=True)

    st.divider()
    sh("📊", "Feature Importance — Which Sensors Drive Predictions")
    imp = bundle.get("importances")
    if imp is None:
        st.info("No feature importance available for this model type.")
    else:
        top  = imp.head(15)[::-1]
        n_top = len(top)
        bar_colors = [
            f"rgba(79,142,247,{0.35 + 0.65 * (i / max(n_top-1,1))})"
            for i in range(n_top)
        ]
        fig_imp = go.Figure(go.Bar(
            x=top.values, y=[str(i) for i in top.index],
            orientation="h",
            marker=dict(color=bar_colors, line=dict(color=C["BLUE"]+"55", width=1)),
            text=[f"{v:.3f}" for v in top.values],
            textposition="outside",
            textfont=dict(color=C["MUTED"], size=10),
        ))
        layout = dark_layout(h=460, t=10, b=30, l=180, r=70)
        layout["xaxis"]["title"] = "Importance Score"
        layout["yaxis"]["tickfont"] = dict(color=C["TEXT"], size=11)
        fig_imp.update_layout(**layout)
        st.plotly_chart(fig_imp, width="stretch")
        st.caption("📌 Higher importance = model relies more on this sensor when detecting faults.")

# ──────────────────────────────────────────────────────────────────
# TAB 4 — Decision Support
# ──────────────────────────────────────────────────────────────────
with tab4:
    rec = recommendations(bundle, run, assessed, t)
    sh("🛠️", "Maintenance Recommendations — For Engineer Review")

    rec_colors = {
        "NORMAL":   (C["NORMAL"],   "rgba(0,210,106,0.08)"),
        "WARNING":  (C["WARNING"],  "rgba(255,179,0,0.08)"),
        "CRITICAL": (C["CRITICAL"], "rgba(255,77,77,0.10)"),
    }
    rc, rbg = rec_colors[status]
    st.markdown(f"""
    <div style="background:{rbg};border:1px solid {rc}44;border-left:4px solid {rc};
                border-radius:12px;padding:14px 18px;margin-bottom:16px;
                font-size:0.9rem;color:{C['TEXT']};line-height:1.6;">
      <strong style="color:{rc};">{status} ·</strong> {rec['timing']}
    </div>
    """, unsafe_allow_html=True)

    sh("🔍", "Variables Deviating Most from Normal")
    st.dataframe(rec["items"], width="stretch", hide_index=True)

    st.markdown(f"""
    <div style="background:{C['CARD']};border:1px solid {C['BORDER']};
                border-left:4px solid {C['BLUE']};border-radius:12px;
                padding:14px 20px;margin-top:20px;">
      <div style="font-size:0.8rem;color:{C['TEXT']};line-height:1.7;">
        🔒 <strong style="color:{C['TEXT']};">Advisory Notice</strong><br>
        <span style="color:{C['MUTED']};">
        All recommendations are <strong>decision-support only</strong> and do not control any equipment.
        Any corrective action must be reviewed, approved, and executed by qualified plant personnel.
        </span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# FOOTER
# ════════════════════════════════════════════════════════════════════
pct_done = (t + 1) / n * 100
st.markdown(f"""
<div class="footer">
  <div>
    🏭 <strong>AI Industrial Maintenance System</strong> &nbsp;·&nbsp;
    Decision-support prototype &nbsp;·&nbsp;
    <span>Does not control plant equipment</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <span>Run <strong>{run_id}</strong></span>
    <span>Progress <strong>{pct_done:.0f}%</strong></span>
    <span>Model <strong>{bundle['classifier_name']}</strong></span>
    <span style="font-family:'JetBrains Mono',monospace;">{now_str}</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Auto-play rerun ──
if play and t < n - 1:
    time.sleep(0.4)
    st.rerun()
