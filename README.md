# 🏭 AI-Based Industrial Maintenance & Process Optimization System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red.svg)](https://streamlit.io/)

An end-to-end **AI-powered decision-support system** for predictive maintenance and process optimization in continuous chemical/petrochemical plants. Built on the **Tennessee Eastman Process (TEP)** benchmark dataset.

> **⚠️ Advisory mode only** — This system provides recommendations for human review. It does not control any plant equipment.

---

## 📋 Table of Contents

- [Features](#-features)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Data Sources](#-data-sources)
- [Pipeline Stages](#-pipeline-stages)
- [Dashboard](#-dashboard)
- [Technologies Used](#-technologies-used)
- [License](#-license)

---

## ✨ Features

- **Real-time Anomaly Detection** — Isolation Forest unsupervised scoring + supervised classifiers
- **Multi-model Classification** — Random Forest, Logistic Regression, XGBoost (auto-selects best F1)
- **Optional LSTM** — PyTorch sequence model over sliding windows for temporal patterns
- **Risk Scoring Engine** — Weighted ensemble of classifier probability and anomaly score with exponential smoothing
- **Early Warning System** — Configurable warning/critical thresholds with detection delay metrics
- **Interactive Dashboard** — Streamlit app with live telemetry, KPI cards, gauge charts, sensor grids, and decision support
- **Equipment-level Recommendations** — Maps deviating sensors to plant equipment with maintenance advice

---

## 📁 Project Structure

```
AI-Based Industrial Maintenance and Process Optimization System/
│
├── app.py                     # Streamlit dashboard (Stage 5)
├── requirements.txt           # Python dependencies
├── LICENSE                    # MIT license
├── README.md
│
├── data/                      # TEP dataset files (see Data Sources below)
│   └── .gitkeep
│
├── models/                    # Generated after training (git-ignored)
│   ├── bundle.joblib          #   trained models, scaler, test data, metrics
│   └── metrics.json           #   P/R/F1 per classifier
│
├── outputs/                   # Generated after training (git-ignored)
│   ├── explore_signals.png    #   EDA signal plots
│   └── risk_trend.png         #   risk trend visualization
│
└── src/
    ├── __init__.py
    ├── data_pipeline.py       # Stage 1-2: data loading, cleaning, feature engineering
    ├── explore_data.py        # EDA and signal visualization
    ├── ml_models.py           # Stage 3: model training, evaluation, scoring
    ├── sequence_model.py      # Stage 3b: LSTM sequence model (optional, needs PyTorch)
    ├── optimizer.py           # Stage 4: risk assessment, thresholds, recommendations
    └── train_model.py         # Training orchestrator script
```

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/KrishnaParalkar-5034/AI-Based-Industrial-Maintenance-and-Process-Optimization-System-.git
cd AI-Based-Industrial-Maintenance-and-Process-Optimization-System-
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Explore the data (optional)

```bash
python src/explore_data.py
```

### 4. Train the models

```bash
python src/train_model.py
```

This generates `models/bundle.joblib` and `models/metrics.json`.

### 5. Launch the dashboard

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 📊 Data Sources

The pipeline tries to load data in this order:

| Priority | Source | Details |
|----------|--------|---------|
| 1 | **Local CSVs** | Place TEP CSV files in `data/` (Kaggle/Harvard Dataverse export with columns `faultNumber, simulationRun, sample, xmeas_1..41, xmv_1..11`) |
| 2 | **Kaggle auto-download** | If no local CSVs found and `kagglehub` is installed, downloads `ma7bakr/tep-dataset` automatically. Needs Kaggle credentials (`~/.kaggle/kaggle.json` or env vars) |
| 3 | **Synthetic fallback** | TEP-style synthetic generator so the prototype always runs. Use real data for meaningful results |

Fault onset is at sample 20 (training) or 160 (testing).

---

## 🔧 Pipeline Stages

| Stage | Module | Description |
|-------|--------|-------------|
| **1-2** | `data_pipeline.py` | Load raw data, clean, engineer rolling-window features (mean, std, min, max, rate-of-change), scale with StandardScaler, 80/20 train-test split by simulation run |
| **3** | `ml_models.py` | Train Random Forest, Logistic Regression, XGBoost classifiers + Isolation Forest anomaly detector. Evaluate with Precision/Recall/F1, select best model |
| **3b** | `sequence_model.py` | *(Optional)* LSTM over 20-step sliding windows for temporal fault detection. Requires PyTorch |
| **4** | `optimizer.py` | Combine classifier probability (65%) and anomaly score (35%) into a smoothed risk score. Map to NORMAL/WARNING/CRITICAL status. Generate equipment-level recommendations |
| **5** | `app.py` | Interactive Streamlit dashboard with live telemetry replay, KPI cards, gauge charts, sensor health grid, alert tracking, model evaluation, and decision support |

---

## 🖥️ Dashboard

The Streamlit dashboard includes four tabs:

- **📊 Live Overview** — KPI cards, gauge charts (risk + health index), risk score timeline with warning/critical zones, live sensor readings grid
- **📈 Telemetry** — Per-sensor time series with normal band (±2σ) overlay, 2-column layout
- **⚠️ Predictions & Alerts** — Alert history table, risk distribution histogram, F1 bar chart, early-warning performance metrics, feature importance
- **🛠️ Decision Support** — Status-coded recommendations, deviating sensors table, equipment-level maintenance advice

### Dashboard Features
- Auto-play mode to simulate live data feed
- Configurable warning/critical thresholds
- Sensor selection for telemetry display
- Run summary panel with warnings/criticals count

---

## 🛠️ Technologies Used

| Category | Tools |
|----------|-------|
| **Language** | Python 3.10+ |
| **ML/AI** | scikit-learn, XGBoost, PyTorch (optional) |
| **Data** | pandas, NumPy |
| **Visualization** | Plotly, Matplotlib |
| **Dashboard** | Streamlit |
| **Data Source** | Tennessee Eastman Process (TEP) dataset |

---

## 📝 Notes

- Train/test splitting is done by **simulation run** (not random rows) to avoid data leakage
- The LSTM model (Stage 3b) is evaluated offline and is not part of the live risk score
- All dashboard recommendations are **advisory only** — any action requires qualified plant personnel



*Built as a decision-support prototype for industrial maintenance and process optimization.*
