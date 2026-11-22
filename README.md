# 🏭 Tennessee Eastman Process (TEP) Predictive Maintenance Platform
### Production-Grade Industrial SCADA Platform for Predictive Maintenance, 21-Class Fault Isolation, & Control-Room Advisory

[![Status](https://img.shields.io/badge/Status-Production--Ready-emerald)](#)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.118-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61dafb)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178c6)](https://www.typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ed)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **SAFETY NOTICE: ADVISORY MODE ONLY (HUMAN-IN-THE-LOOP)**  
> This platform is an industrial decision-support system. It provides real-time telemetry analytics, early-warning risk scoring, root-cause isolation, and prescriptive guidance. It **never performs automated physical valve or actuator manipulation**. All setpoint adjustments must be validated and entered manually by certified Distributed Control System (DCS) console operators.

---

## 1. System Architecture

The platform provides a production-grade 3-service monorepo alongside the initial exploratory prototype:

```
AI-Based-Industrial-Maintenance-and-Process-Optimization-System-/
├── ml/                      # Machine Learning Core & Signal Quality
│   ├── config.py            # Ground-truth 52 variables, P&ID units, fault definitions
│   ├── data_pipeline.py     # Causal ffill cleaning, multi-scale features, run-stratified split
│   ├── signal_quality.py    # Frozen sensor (var=0), dropout/NaN, spike (|z|>8) monitor
│   ├── models.py            # 3-pillar ensemble (XGBoost, LSTM-FCN, Autoencoder, Stacking)
│   ├── explainability.py    # TreeSHAP exact attributions, P&ID unit rollup, TTC slope
│   ├── alarms.py            # ANSI/ISA-18.2 deadband hysteresis & alarm flood suppression
│   └── train_colab.py       # Standalone Colab/GPU training pipeline & early-warning audit
├── backend/                 # Industrial FastAPI & Telemetry Historian
│   ├── main.py              # REST API, WebSockets, Prometheus metrics (/metrics)
│   ├── engine.py            # ProcessInferenceEngine, 50-sample buffer, real-time scoring
│   ├── adapters.py          # Telemetry feeds (Historical replay, live AR(1) simulation)
│   ├── db.py                # TimescaleDB/PostgreSQL ORM with SQLite WAL fallback
│   └── schemas.py           # Pydantic v2 data transfer schemas
├── frontend/                # Control-Room React 18+ SPA (Vite + Tailwind CSS + Recharts)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx                 # Persistent header, WS status, playback scrubber
│   │   │   ├── PidDigitalTwin.tsx         # Interactive Vector SVG P&ID Digital Twin
│   │   │   ├── CockpitView.tsx            # View 1: Plant Cockpit, Health Gauge, Risk Timeline
│   │   │   ├── TelemetryExplorerView.tsx  # View 2: Multi-channel plots, ±2σ envelopes, flags
│   │   │   ├── DiagnosticsView.tsx        # View 3: 21-Class isolation, TreeSHAP waterfall
│   │   │   └── AlarmConsoleView.tsx       # View 4: ISA-18.2 console, notes, handover export
│   │   ├── api.ts                         # Type-safe backend API client
│   │   ├── useTelemetrySocket.ts          # Sub-second WebSocket live stream hook
│   │   └── types.ts                       # TypeScript interfaces matching backend contracts
├── notebooks/               # Colab GPU Training Workflow
│   └── train_on_colab.ipynb # Ready-to-run Google Colab GPU training notebook
├── docker/                  # Multi-Stage Production Containers
│   ├── Dockerfile.backend   # Python 3.11-slim, non-root user, healthchecked
│   ├── Dockerfile.frontend  # Node 22 build -> Alpine Nginx with WebSocket upgrade
│   └── nginx.conf           # Production reverse proxy for /api, /ws, and SPA routing
├── models/                  # Serialized Production Artifacts (Hot-Swappable)
│   ├── bundle.joblib        # Scaler, calibrated XGBoost binary/multi, meta-learner
│   ├── lstm_fcn.pt          # PyTorch LSTM-FCN weights
│   ├── autoencoder.pt       # PyTorch Dense Autoencoder weights
│   ├── metrics.json         # Full evaluation benchmarks & early-warning audit
│   └── replay_sample.parquet# 52-channel slim held-out replay runs (22 runs)
├── tests/                   # Automated Pytest Suite (Anti-Leakage & Integration)
├── docker-compose.yml       # Production 3-container orchestration (TimescaleDB, API, Nginx)
├── app.py                   # Exploratory Streamlit Dashboard (Prototype)
└── src/                     # Exploratory prototype pipeline & baseline models
```

---

## 2. 52-Variable Process Mapping & P&ID Topology

The platform maps all 52 chemical engineering variables across 6 primary physical units:

| Physical P&ID Unit | Measured Telemetry Channels (`xmeas_1` – `xmeas_41`) | Manipulated Control Valves (`xmv_1` – `xmv_11`) |
| :--- | :--- | :--- |
| **1. Feed & Purge System** | `xmeas_1` (A Feed Flow), `xmeas_2` (D Feed Flow), `xmeas_3` (E Feed Flow), `xmeas_4` (A & C Feed Flow), `xmeas_10` (Purge Rate), `xmeas_29`–`xmeas_36` (Purge Gas Composition A–H) | `xmv_1` (D Feed Valve), `xmv_2` (E Feed Valve), `xmv_3` (A Feed Valve), `xmv_4` (A & C Feed Valve), `xmv_6` (Purge Valve) |
| **2. Reactor** | `xmeas_6` (Reactor Feed Rate), `xmeas_7` (Reactor Pressure), `xmeas_8` (Reactor Level), `xmeas_9` (Reactor Temperature), `xmeas_21` (Cooling Water Outlet Temp), `xmeas_23`–`xmeas_28` (Feed Composition A–F) | `xmv_10` (Reactor Cooling Water Valve) |
| **3. Product Condenser** | `xmeas_22` (Condenser Cooling Water Outlet Temp) | `xmv_11` (Condenser Cooling Water Valve) |
| **4. Vapor-Liquid Separator** | `xmeas_11` (Separator Temp), `xmeas_12` (Separator Level), `xmeas_13` (Separator Pressure), `xmeas_14` (Separator Underflow) | `xmv_7` (Separator Liquid Flow Valve) |
| **5. Recycle Compressor** | `xmeas_5` (Recycle Flow), `xmeas_20` (Compressor Work) | `xmv_5` (Compressor Recycle Valve) |
| **6. Product Stripper** | `xmeas_15` (Stripper Level), `xmeas_16` (Stripper Pressure), `xmeas_17` (Stripper Product Flow), `xmeas_18` (Stripper Temp), `xmeas_19` (Stripper Steam Flow), `xmeas_37`–`xmeas_41` (Product Composition D–H) | `xmv_8` (Stripper Product Valve), `xmv_9` (Stripper Steam Valve) |

**Process Piping Topology:**  
`Feed System` $\to$ `Reactor` $\to$ `Product Condenser` $\to$ `Vapor-Liquid Separator` $\to$ liquid bottoms to `Product Stripper` (outputting products G/H) + overhead vapor splitting to `Purge` and `Recycle Compressor` looping back into `Reactor`.

---

## 3. Verified Benchmark Metrics (Held-Out Test Set)

Evaluated on held-out test runs from the canonical Downs & Vogel Tennessee Eastman Process dataset (`ma7bakr/tep-dataset`, `kaggle_dat`) with strict run-stratified zero-leakage splitting ($N = 22$ independent test runs, 20,480 samples across `d00_te` through `d21_te`):

| Model Component / Architecture | Precision | Recall | F1 Score | ROC-AUC | Engineering Role |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Pillar 1: XGBoost (Binary Fault Detector)** | **0.8892** | **0.8318** | **0.8595** | **0.8232** | Platt-calibrated gradient boosting over 364 rolling features |
| **Pillar 1: XGBoost (21-Class Fault Isolator)** | — | — | **0.6667** *(Macro)* | — | 21-class multiclass root-cause diagnosis |
| **Pillar 2: PyTorch LSTM-FCN (Temporal)** | **1.0000** | **0.1881** | **0.3166** | **0.7693** | 20-step sequence, 2-layer LSTM + Conv1D temporal modeling |
| **Pillar 3: PyTorch Dense Autoencoder** | **0.9988** | **0.2030** | **0.3375** | **0.7621** | Novelty safety net trained exclusively on normal operating rows |
| **★ Stacked Heterogeneous Ensemble** | **0.9853** | **0.5362** | **0.6945** | **0.8703** | 4-feature meta-learner $[P_{\text{xgb}}, P_{\text{lstm}}, S_{\text{anom}}, P_{\text{multi}}]$ with quantile shift |

### Early-Warning & Detection Delay Audit:
* **Detectable Fault Detection Rate:** **88.9%** (16 of 18 detectable faults alarmed at risk $\ge 0.70$)
* **Overall Fault Detection Rate:** **76.2%** (16 of 21 faults, accounting for Downs & Vogel low-SNR Faults 3, 9, 15)
* **Median Detection Delay:** **47.5 samples (~142.5 minutes post-onset)**
* **Normal-Run False Alarms:** **0** on clean run `F0_R1_d00_te` (Normal FPR: **4.58%**, strictly $< 5.0\%$)
* **Pre-Onset False Alarms:** **0 / 21 runs** on pre-disturbance samples $t < 160$ (Pre-onset FPR: **2.68%**)
* *Zero-Leakage Guarantee:* All meta-learner weights, calibration shifts, and thresholds fitted strictly on validation split (`yval == 0`); zero test set contamination.

---

## 4. Quickstart Guide (Local Development Without Docker)

### Prerequisites:
* Python 3.11+
* Node.js v18+ & npm v9+

### 1. Backend Setup & Startup:
```bash
# From workspace root
pip install -r requirements.txt

# Start FastAPI backend (defaults to local SQLite WAL historian)
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
* Backend API Documentation: `http://localhost:8000/docs`
* Prometheus Metrics: `http://localhost:8000/metrics`
* Health Check: `http://localhost:8000/health`

### 2. Frontend Setup & Startup:
```bash
# In a separate terminal
cd frontend
npm install
npm run dev
```
* Open your browser at: `http://localhost:3000`
* Vite automatically proxies `/api` and `/ws` to `http://localhost:8000` with zero CORS configuration required.

### 3. Exploratory Streamlit Dashboard (Optional):
The original prototype dashboard remains available for exploratory EDA:
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 5. Production Docker Deployment

Deploy the complete multi-service stack with persistent TimescaleDB / PostgreSQL, backend API, and Nginx reverse proxy via Docker Compose:

```bash
# Build and launch all 3 production services
docker compose up --build -d

# Check container health status
docker compose ps

# View live consolidated service logs
docker compose logs -f
```

### Services Deployed:
* **Frontend Web UI & Nginx Reverse Proxy:** `http://localhost:3000`
* **FastAPI Backend REST & WebSocket:** `http://localhost:8000`
* **TimescaleDB Historian:** `localhost:5432` (`tep_db`, user: `tep_user`, password: `tep_password`)

### Hot-Swapping Model Weights Without Container Rebuilds:
The backend container mounts `./models:/app/models` as a bind volume. Whenever updated model weights are produced from Google Colab:
1. Copy `bundle.joblib`, `lstm_fcn.pt`, `autoencoder.pt`, and `metrics.json` into `./models/`.
2. Restart the backend container: `docker compose restart backend`.
3. The inference engine reloads the new weights immediately with zero image rebuilding.

---

## 6. Google Colab GPU Training Workflow

To train large-scale models on the full historical Downs & Vogel dataset using Google Colab free T4/A100 GPUs:

1. Open `notebooks/train_on_colab.ipynb` in [Google Colab](https://colab.research.google.com).
2. Set runtime hardware accelerator: **Runtime > Change runtime type > T4 GPU**.
3. Run all notebook cells. The script will:
   - Download the official Downs & Vogel dataset (`ma7bakr/tep-dataset` via KaggleHub or direct synthetic generator).
   - Execute zero-leakage causal forward-fill and rolling feature engineering ($W=10, 30$).
   - Train Pillar 1 (XGBoost), Pillar 2 (LSTM-FCN with AMP mixed precision), Pillar 3 (Autoencoder), and the calibrated Stacking Meta-Learner.
   - Run the early-warning lead-time audit.
   - Package all production artifacts into `tep_artifacts.zip`.
4. Download `tep_artifacts.zip` and extract its contents into your local `models/` directory.

---

## 7. Automated Testing & Verification Suite

Execute the full suite of anti-leakage, signal quality, model architecture, and API/WebSocket contract tests:

```bash
# Run all 33 unit, regression, and integration tests
python -m pytest tests -v

# Run frontend TypeScript type-checker & production build
cd frontend && npm run build
```

---

## 8. License & Acknowledgements

* **License:** MIT License (see [LICENSE](LICENSE)).
* **Benchmark Origin:** Downs, J. J., & Vogel, E. F. (1993). *A plant-wide industrial process control problem.* Computers & Chemical Engineering, 17(3), 245-255.

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

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Krishna Paralkar
