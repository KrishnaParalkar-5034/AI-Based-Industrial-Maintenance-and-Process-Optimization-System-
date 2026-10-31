# AI-Based Industrial Maintenance & Process Optimization (prototype)

Decision-support system (human review only) for continuous chemical / petrochemical plants.

```
ai_maintenance/
├── app.py                  # Stage 5  Streamlit dashboard
├── requirements.txt
├── data/                   # drop real TEP CSVs here (optional)
└── src/
    ├── data_pipeline.py    # Stage 1-2 load, clean, features, scaler, 80/20 split
    ├── ml_models.py        # Stage 3   RF / LogReg / XGBoost + Isolation Forest, P/R/F1
    ├── sequence_model.py   # Stage 3b  LSTM over sliding windows (optional, needs torch)
    ├── optimizer.py        # Stage 4   risk score, status, recommendations
    ├── explore_data.py
    └── train_model.py
```

## Quick start

```bash
pip install -r requirements.txt
python src/explore_data.py
python src/train_model.py
streamlit run app.py
```

## Using the real Tennessee Eastman data

The pipeline tries to load data in this order:

1. **Local CSVs** — Place TEP CSV files (Kaggle / Harvard Dataverse export with columns `faultNumber, simulationRun, sample, xmeas_1..41, xmv_1..11`) in `data/`, then re-run `train_model.py`.
2. **Kaggle auto-download** — If no local CSVs are found and `kagglehub` is installed, the pipeline automatically downloads `ma7bakr/tep-dataset` from Kaggle and reads its raw `.dat` files (`d00.dat`..`d21.dat`, `d00_te.dat`..`d21_te.dat`). You need Kaggle credentials set up (via `KAGGLE_USERNAME` / `KAGGLE_KEY` env vars or `~/.kaggle/kaggle.json`).
3. **Synthetic fallback** — If both of the above fail, a TEP-style **synthetic** generator is used so the prototype always runs. Report results only on real data.

Fault onset is assumed at sample 20 (training files) or 160 (testing files).

## Notes
- Splitting is by simulation run (not random rows) to avoid leakage between train and test.
- **LSTM (Stage 3b)** — `sequence_model.py` trains a PyTorch LSTM over 20-step sliding windows of the engineered features and reports its Precision / Recall / F1 next to the tabular models. `torch` is optional: without it the model is skipped and only the metrics of the models that did run are stored in `models/metrics.json`. The LSTM is evaluated offline and is not part of the live risk score in the dashboard.
