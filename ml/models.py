"""
3-Pillar Heterogeneous ML Ensemble & 21-Class Fault Diagnosis for Industrial Telemetry.
Pillar 1: XGBoost (Binary Fault Detector + 21-Class Fault Isolator)
Pillar 2: PyTorch LSTM-FCN (Temporal Sequence Model over sliding windows)
Pillar 3: PyTorch Dense Autoencoder & Isolation Forest (Unsupervised Safety Net)
Unified by a regularized Stacking Meta-Learner with Platt calibration.
"""
import copy
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from .config import TEP_FAULT_DEFINITIONS

# Device configuration
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CUDA_AVAILABLE = torch.cuda.is_available()


# ==============================================================================
# PILLAR 2: PyTorch LSTM-FCN Architecture
# ==============================================================================

class SqueezeExcitation1d(nn.Module):
    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        self.fc1 = nn.Linear(channels, max(channels // reduction, 8))
        self.fc2 = nn.Linear(max(channels // reduction, 8), channels)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (B, C, L)
        b, c, _ = x.shape
        w = torch.mean(x, dim=2) # Global average pool across length -> (B, C)
        w = self.sigmoid(self.fc2(self.relu(self.fc1(w)))).unsqueeze(-1)
        return x * w


class LSTMFCNNet(nn.Module):
    """
    Parallel LSTM + 3-Block 1D-CNN with Squeeze-and-Excitation & Regularized Dropout.
    Input: (Batch, Sequence_Length, Features)
    """
    def __init__(self, n_features: int, hidden_dim: int = 64):
        super().__init__()
        # Branch A: 2-layer LSTM
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            dropout=0.3 if 2 > 1 else 0.0
        )
        # Branch B: 1D-CNN over channels (Features treated as channels, Length as L)
        self.conv1 = nn.Conv1d(n_features, 64, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(64)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(128)
        self.conv3 = nn.Conv1d(128, 64, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(64)
        self.drop = nn.Dropout(0.3)
        self.se = SqueezeExcitation1d(64)
        self.gap = nn.AdaptiveAvgPool1d(1)

        self.relu = nn.ReLU()
        self.head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(hidden_dim + 64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # LSTM branch: (B, L, F)
        out_lstm, _ = self.lstm(x)
        lstm_feat = out_lstm[:, -1, :] # Last timestep (B, hidden_dim)

        # CNN branch: expects (B, Channels, Length) -> transpose (B, F, L)
        x_cnn = x.permute(0, 2, 1)
        c1 = self.relu(self.bn1(self.conv1(x_cnn)))
        c2 = self.relu(self.bn2(self.conv2(c1)))
        c3 = self.relu(self.bn3(self.conv3(c2)))
        c_drop = self.drop(c3)
        c_se = self.se(c_drop)
        cnn_feat = self.gap(c_se).squeeze(-1) # (B, 64)

        # Fusion
        fused = torch.cat([lstm_feat, cnn_feat], dim=-1)
        logits = self.head(fused).squeeze(-1)
        return logits


# ==============================================================================
# PILLAR 3: PyTorch Dense Autoencoder
# ==============================================================================

class DenseAutoencoder(nn.Module):
    """
    Symmetric multi-layer bottleneck Autoencoder for novelty detection.
    Trained strictly on normal steady-state operation.
    """
    def __init__(self, n_features: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(n_features, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, 24),
            nn.ReLU(),
            nn.Linear(24, 12) # Bottleneck
        )
        self.decoder = nn.Sequential(
            nn.Linear(12, 24),
            nn.ReLU(),
            nn.Linear(24, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, n_features)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        return self.decoder(z)


# ==============================================================================
# SEQUENCE UTILITIES
# ==============================================================================

def create_sliding_sequences(
    df: pd.DataFrame,
    feature_cols: List[str],
    scaler,
    window: int = 20,
    stride: int = 5,
    balance_normal_stride: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """Slice run-based continuous frames into 3D sequence tensors (N, window, features)."""
    df_sorted = df.sort_values(["run_id", "sample"]).reset_index(drop=True)
    scaled = scaler.transform(df_sorted[feature_cols].values.astype(np.float32))
    flags = df_sorted["fault_flag"].values.astype(np.float32)

    xs, ys = [], []
    for _, idxs in df_sorted.groupby("run_id").indices.items():
        idxs = np.sort(idxs)
        n = len(idxs)
        if n < window:
            continue
        for start in range(0, n - window + 1):
            is_normal = (flags[idxs[start + window - 1]] == 0)
            # If balance_normal_stride, sample every step for normal, every stride steps for fault
            if balance_normal_stride:
                if not is_normal and (start % stride != 0):
                    continue
            else:
                if start % stride != 0:
                    continue

            xs.append(scaled[idxs[start:start + window]])
            ys.append(flags[idxs[start + window - 1]])

    if not xs:
        # Fallback dummy sequence if dataset too small
        return np.zeros((1, window, len(feature_cols)), dtype=np.float32), np.zeros(1, dtype=np.float32)

    return np.stack(xs).astype(np.float32), np.asarray(ys, dtype=np.float32)


def compute_lstm_fcn_probs_for_df(
    model: LSTMFCNNet,
    df: pd.DataFrame,
    feature_cols: List[str],
    scaler,
    window: int = 20
) -> np.ndarray:
    """Compute continuous LSTM-FCN sigmoid probabilities for every row in a run-grouped dataframe."""
    model.eval()
    scaled = scaler.transform(df[feature_cols].values.astype(np.float32))
    n_samples = len(df)
    probs = np.zeros(n_samples, dtype=np.float32)

    with torch.no_grad():
        for _, idxs in df.groupby("run_id").indices.items():
            idxs = np.sort(idxs)
            m = len(idxs)
            batch_seqs = []
            sample_map = []
            for i in range(m):
                actual_row_idx = idxs[i]
                start_pos = max(0, i - window + 1)
                seq_slice = scaled[idxs[start_pos:i + 1]]
                if len(seq_slice) < window:
                    pad_len = window - len(seq_slice)
                    first_elem = seq_slice[0:1]
                    seq_slice = np.vstack([np.repeat(first_elem, pad_len, axis=0), seq_slice])
                batch_seqs.append(seq_slice)
                sample_map.append(actual_row_idx)

            batch_arr = np.stack(batch_seqs).astype(np.float32)
            for b_start in range(0, len(batch_arr), 512):
                b_chunk = torch.from_numpy(batch_arr[b_start:b_start + 512]).to(DEVICE)
                logits = model(b_chunk)
                p = torch.sigmoid(logits).cpu().numpy()
                for local_idx, p_val in enumerate(p):
                    probs[sample_map[b_start + local_idx]] = float(p_val)
    return probs


# ==============================================================================
# TRAINING PIPELINE
# ==============================================================================

def compute_binary_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: Optional[np.ndarray] = None) -> Dict[str, Any]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    metrics = {
        "precision": float(round(precision_score(y_true, y_pred, zero_division=0), 4)),
        "recall": float(round(recall_score(y_true, y_pred, zero_division=0), 4)),
        "f1": float(round(f1_score(y_true, y_pred, zero_division=0), 4)),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)
    }
    if y_prob is not None and len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = float(round(roc_auc_score(y_true, y_prob), 4))
    else:
        metrics["roc_auc"] = 0.5
    return metrics


def train_pillar1_xgboost(
    ds: Dict[str, Any],
    seed: int = 42
) -> Tuple[XGBClassifier, Any, XGBClassifier, Dict[str, Any], Dict[str, Any]]:
    """Train XGBoost binary fault detector and 21-class fault isolator with Platt calibration."""
    Xtr, ytr_bin, ytr_multi = ds["X_train"], ds["y_train_bin"], ds["y_train_multi"]
    Xval, yval_bin, yval_multi = ds["X_val"], ds["y_val_bin"], ds["y_val_multi"]
    Xte, yte_bin, yte_multi = ds["X_test"], ds["y_test_bin"], ds["y_test_multi"]

    device_arg = "cuda" if CUDA_AVAILABLE else "cpu"

    print(f"[models] Training Pillar 1: XGBoost Binary on {device_arg}...")
    n_norm = int((ytr_bin == 0).sum())
    n_flt = int((ytr_bin == 1).sum())
    scale_pos_weight = float(n_norm / max(1, n_flt))
    sw_tr = compute_sample_weight("balanced", ytr_bin)
    sw_val = compute_sample_weight("balanced", yval_bin)

    xgb_bin = XGBClassifier(
        n_estimators=140,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.6,
        min_child_weight=20,
        reg_alpha=1.0,
        reg_lambda=3.0,
        scale_pos_weight=scale_pos_weight,
        tree_method="hist",
        device=device_arg,
        eval_metric="logloss",
        random_state=seed
    )
    xgb_bin.fit(Xtr, ytr_bin, sample_weight=sw_tr, eval_set=[(Xval, yval_bin)], sample_weight_eval_set=[sw_val], verbose=False)

    # Calibrate probability predictions with balanced sample weights on validation set
    calibrated_xgb = CalibratedClassifierCV(estimator=xgb_bin, method="sigmoid", cv="prefit")
    calibrated_xgb.fit(Xval, yval_bin, sample_weight=sw_val)

    p_test_bin = calibrated_xgb.predict_proba(Xte)[:, 1]
    metrics_bin = compute_binary_metrics(yte_bin, (p_test_bin >= 0.5).astype(int), p_test_bin)

    print(f"[models] Training Pillar 1: XGBoost 21-Class Isolator on {device_arg}...")
    # Map classes to dense 0..K-1
    unique_classes = sorted(np.unique(ytr_multi))
    class_to_idx = {c: i for i, c in enumerate(unique_classes)}
    idx_to_class = {i: c for i, c in enumerate(unique_classes)}
    ytr_dense = np.array([class_to_idx[c] for c in ytr_multi])
    yval_dense = np.array([class_to_idx.get(c, 0) for c in yval_multi])
    yte_dense = np.array([class_to_idx.get(c, 0) for c in yte_multi])

    xgb_multi = XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.65,
        tree_method="hist",
        device=device_arg,
        objective="multi:softprob",
        eval_metric="mlogloss",
        random_state=seed
    )
    xgb_multi.fit(Xtr, ytr_dense, eval_set=[(Xval, yval_dense)], verbose=False)
    pred_multi = xgb_multi.predict(Xte)
    metrics_multi = {
        "macro_f1": float(round(f1_score(yte_dense, pred_multi, average="macro", zero_division=0), 4)),
        "weighted_f1": float(round(f1_score(yte_dense, pred_multi, average="weighted", zero_division=0), 4))
    }

    # Per-fault F1 breakdown
    per_fault_f1 = {}
    for idx_cls, c_val in idx_to_class.items():
        mask = (yte_dense == idx_cls)
        if mask.any():
            per_fault_f1[int(c_val)] = float(round(
                f1_score(mask, pred_multi == idx_cls, zero_division=0), 4
            ))
    metrics_multi["per_fault_f1"] = per_fault_f1

    return xgb_bin, calibrated_xgb, xgb_multi, metrics_bin, metrics_multi


def train_pillar2_lstm_fcn(
    ds: Dict[str, Any],
    epochs: int = 8,
    batch_size: int = 256,
    lr: float = 1e-3,
    seed: int = 42
) -> Tuple[LSTMFCNNet, Dict[str, Any]]:
    """Train PyTorch LSTM-FCN sequence model with AMP, balanced sequence stride, and validation checkpointing."""
    torch.manual_seed(seed)
    Xtr_seq, ytr_seq = create_sliding_sequences(ds["train"], ds["features"], ds["scaler"], balance_normal_stride=True)
    Xval_seq, yval_seq = create_sliding_sequences(ds["val"], ds["features"], ds["scaler"], balance_normal_stride=False)
    Xte_seq, yte_seq = create_sliding_sequences(ds["test"], ds["features"], ds["scaler"], balance_normal_stride=False)

    n_features = len(ds["features"])
    model = LSTMFCNNet(n_features).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-3)

    pos_w = float((ytr_seq == 0).sum() / max(1, (ytr_seq == 1).sum()))
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_w], device=DEVICE))

    loader = DataLoader(
        TensorDataset(torch.from_numpy(Xtr_seq), torch.from_numpy(ytr_seq)),
        batch_size=batch_size,
        shuffle=True
    )

    print(f"[models] Training Pillar 2: LSTM-FCN on {DEVICE} ({epochs} epochs)...")
    scaler_amp = torch.amp.GradScaler("cuda") if CUDA_AVAILABLE else None

    best_val_auc = -1.0
    best_weights = None

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for bx, by in loader:
            bx, by = bx.to(DEVICE), by.to(DEVICE)
            optimizer.zero_grad()

            if CUDA_AVAILABLE and scaler_amp is not None:
                with torch.amp.autocast("cuda", dtype=torch.float16):
                    logits = model(bx)
                    loss = criterion(logits, by)
                scaler_amp.scale(loss).backward()
                scaler_amp.step(optimizer)
                scaler_amp.update()
            else:
                logits = model(bx)
                loss = criterion(logits, by)
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * len(by)

        # Validation checkpointing on ROC-AUC
        if len(yval_seq) > 1 and len(np.unique(yval_seq)) > 1:
            model.eval()
            with torch.no_grad():
                val_x = torch.from_numpy(Xval_seq).to(DEVICE)
                val_logits = model(val_x)
                val_probs = torch.sigmoid(val_logits).cpu().numpy()
                val_auc = float(roc_auc_score(yval_seq, val_probs))
                if val_auc > best_val_auc:
                    best_val_auc = val_auc
                    best_weights = copy.deepcopy(model.state_dict())

    # Load best checkpoint if available
    if best_weights is not None:
        model.load_state_dict(best_weights)

    # Evaluation
    model.eval()
    with torch.no_grad():
        te_x = torch.from_numpy(Xte_seq).to(DEVICE)
        logits_te = model(te_x)
        probs_te = torch.sigmoid(logits_te).cpu().numpy()
        pred_te = (probs_te >= 0.5).astype(int)

    metrics = compute_binary_metrics(yte_seq.astype(int), pred_te, probs_te)
    return model, metrics


def train_pillar3_autoencoder(
    ds: Dict[str, Any],
    epochs: int = 10,
    batch_size: int = 256,
    lr: float = 1e-3,
    seed: int = 42
) -> Tuple[DenseAutoencoder, IsolationForest, float, float, Dict[str, Any]]:
    """Train dense Autoencoder & Isolation Forest exclusively on normal operating rows."""
    torch.manual_seed(seed)
    Xtr, ytr = ds["X_train"], ds["y_train_bin"]
    Xte, yte = ds["X_test"], ds["y_test_bin"]

    Xtr_norm = Xtr[ytr == 0]
    n_features = Xtr.shape[1]

    ae = DenseAutoencoder(n_features).to(DEVICE)
    opt = torch.optim.Adam(ae.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    loader = DataLoader(
        TensorDataset(torch.from_numpy(Xtr_norm).float()),
        batch_size=batch_size,
        shuffle=True
    )

    print(f"[models] Training Pillar 3: Autoencoder on normal data ({epochs} epochs)...")
    for epoch in range(epochs):
        ae.train()
        for (bx,) in loader:
            bx = bx.to(DEVICE)
            opt.zero_grad()
            recon = ae(bx)
            loss = loss_fn(recon, bx)
            loss.backward()
            opt.step()

    # Determine normalization bounds from normal train set
    ae.eval()
    with torch.no_grad():
        x_tr_t = torch.from_numpy(Xtr_norm).float().to(DEVICE)
        mse_tr = torch.mean((ae(x_tr_t) - x_tr_t) ** 2, dim=-1).cpu().numpy()
        p50, p995 = float(np.percentile(mse_tr, 50)), float(np.percentile(mse_tr, 99.5))

        x_te_t = torch.from_numpy(Xte).float().to(DEVICE)
        mse_te = torch.mean((ae(x_te_t) - x_te_t) ** 2, dim=-1).cpu().numpy()
        anom_score_te = np.clip((mse_te - p50) / (p995 - p50 + 1e-6), 0.0, 1.0)

    metrics_ae = compute_binary_metrics(yte, (anom_score_te > 0.85).astype(int), anom_score_te)

    # Lightweight Isolation Forest fallback
    iso = IsolationForest(n_estimators=150, contamination=0.01, random_state=seed, n_jobs=-1)
    iso.fit(Xtr_norm)

    return ae, iso, p50, p995, metrics_ae


def train_stacking_metalearner(
    xgb_calibrated: Any,
    lstm_fcn: LSTMFCNNet,
    autoencoder: DenseAutoencoder,
    ae_lo: float,
    ae_hi: float,
    ds: Dict[str, Any],
    xgb_multi: Optional[Any] = None
) -> Tuple[Any, Dict[str, Any], Dict[str, float]]:
    """Fit a regularized Logistic Regression stacking meta-learner on [P_xgb, P_lstm, S_anomaly, P_multi_fault]."""
    Xval, yval = ds["X_val"], ds["y_val_bin"]
    Xte, yte = ds["X_test"], ds["y_test_bin"]

    # 1. Calibrated XGBoost probability
    p_xgb_val = xgb_calibrated.predict_proba(Xval)[:, 1]
    p_xgb_te = xgb_calibrated.predict_proba(Xte)[:, 1]

    # 2. Continuous LSTM-FCN probability
    p_lstm_val = compute_lstm_fcn_probs_for_df(lstm_fcn, ds["val"], ds["features"], ds["scaler"])
    p_lstm_te = compute_lstm_fcn_probs_for_df(lstm_fcn, ds["test"], ds["features"], ds["scaler"])

    # 3. Continuous Autoencoder anomaly score
    autoencoder.eval()
    with torch.no_grad():
        xval_t = torch.from_numpy(Xval).float().to(DEVICE)
        mse_val = torch.mean((autoencoder(xval_t) - xval_t) ** 2, dim=-1).cpu().numpy()
        p_anom_val = np.clip((mse_val - ae_lo) / (ae_hi - ae_lo + 1e-6), 0.0, 1.0)

        xte_t = torch.from_numpy(Xte).float().to(DEVICE)
        mse_te = torch.mean((autoencoder(xte_t) - xte_t) ** 2, dim=-1).cpu().numpy()
        p_anom_te = np.clip((mse_te - ae_lo) / (ae_hi - ae_lo + 1e-6), 0.0, 1.0)

    # 4. Multi-class fault probability (P(Fault > 0)) to capture localized disturbances
    if xgb_multi is not None:
        p_multi_val = np.clip(1.0 - xgb_multi.predict_proba(Xval)[:, 0], 0.0, 1.0)
        p_multi_te = np.clip(1.0 - xgb_multi.predict_proba(Xte)[:, 0], 0.0, 1.0)
        meta_X_val = np.column_stack([p_xgb_val, p_lstm_val, p_anom_val, p_multi_val])
        meta_X_te = np.column_stack([p_xgb_te, p_lstm_te, p_anom_te, p_multi_te])
    else:
        meta_X_val = np.column_stack([p_xgb_val, p_lstm_val, p_anom_val])
        meta_X_te = np.column_stack([p_xgb_te, p_lstm_te, p_anom_te])

    sw_val = compute_sample_weight("balanced", yval)
    meta_learner = LogisticRegression(C=1.0, class_weight="balanced", max_iter=300, random_state=42)
    meta_learner.fit(meta_X_val, yval, sample_weight=sw_val)

    # ZERO DATA LEAKAGE: Calibrate decision threshold STRICTLY on validation split normal samples (yval == 0)
    raw_val = meta_learner.decision_function(meta_X_val)
    raw_te = meta_learner.decision_function(meta_X_te)

    val_norm_mask = (yval == 0)
    if val_norm_mask.any():
        norm_raw = raw_val[val_norm_mask]
        shift = float(np.mean(norm_raw) + 3.0 * np.std(norm_raw))
    else:
        shift = float(np.percentile(raw_val, 50.0))

    scale = 1.25
    cal_params = {"shift": shift, "scale": scale}

    p_ensemble = 1.0 / (1.0 + np.exp(-scale * (raw_te - shift)))
    metrics = compute_binary_metrics(yte, (p_ensemble >= 0.5).astype(int), p_ensemble)

    return meta_learner, metrics, cal_params


def train_all_models(ds: Dict[str, Any], seed: int = 42) -> Dict[str, Any]:
    """Execute complete 3-pillar training pipeline and bundle artifacts."""
    xgb_bin, xgb_calibrated, xgb_multi, m_xgb, m_multi = train_pillar1_xgboost(ds, seed=seed)
    lstm_fcn, m_lstm = train_pillar2_lstm_fcn(ds, seed=seed)
    ae, iso, ae_lo, ae_hi, m_ae = train_pillar3_autoencoder(ds, seed=seed)
    meta_learner, m_ensemble, cal_params = train_stacking_metalearner(
        xgb_calibrated, lstm_fcn, ae, ae_lo, ae_hi, ds, xgb_multi=xgb_multi
    )

    # Compile benchmark metrics
    metrics_report = {
        "Pillar 1: XGBoost (Binary)": m_xgb,
        "Pillar 1: XGBoost (21-Class Multiclass)": m_multi,
        "Pillar 2: LSTM-FCN (Temporal Sequence)": m_lstm,
        "Pillar 3: Autoencoder (Novelty MSE)": m_ae,
        "Stacked Heterogeneous Ensemble": m_ensemble,
    }

    # Extract global TreeSHAP / importance
    importances = pd.Series(xgb_bin.feature_importances_, index=ds["features"]).sort_values(ascending=False)

    bundle = {
        "xgb_binary": xgb_bin,
        "xgb_calibrated": xgb_calibrated,
        "xgb_multi": xgb_multi,
        "meta_learner": meta_learner,
        "meta_calibration": cal_params,
        "iso_forest": iso,
        "ae_bounds": {"lo": ae_lo, "hi": ae_hi},
        "scaler": ds["scaler"],
        "features": ds["features"],
        "sensors": ds["sensors"],
        "normal_mean": ds["normal_mean"],
        "normal_std": ds["normal_std"],
        "source": ds["source"],
        "test": ds["test"],
        "metrics": metrics_report,
        "feature_importances": importances.to_dict(),
    }

    return {
        "bundle": bundle,
        "lstm_fcn": lstm_fcn,
        "autoencoder": ae,
        "metrics": metrics_report
    }


def score_frame_realtime(
    bundle: Dict[str, Any],
    autoencoder: Optional[nn.Module],
    df: pd.DataFrame,
    lstm_fcn: Optional[nn.Module] = None,
    mode: str = "stacked_ensemble"
) -> Dict[str, Any]:
    """
    Score live telemetry frame(s):
      Computes unified risk, individual pillar scores, and 21-class fault predictions.
    """
    X = bundle["scaler"].transform(df[bundle["features"]].values.astype(np.float32))

    # Pillar 1 (Calibrated)
    cal_xgb = bundle.get("xgb_calibrated", bundle["xgb_binary"])
    p_xgb = cal_xgb.predict_proba(X)[:, 1]
    multi_probs = bundle["xgb_multi"].predict_proba(X)
    multi_preds = np.argmax(multi_probs, axis=1)

    # Pillar 3 (Autoencoder or Isolation Forest)
    if autoencoder is not None:
        autoencoder.eval()
        with torch.no_grad():
            xt = torch.from_numpy(X).float().to(DEVICE)
            mse = torch.mean((autoencoder(xt) - xt) ** 2, dim=-1).cpu().numpy()
            lo = bundle["ae_bounds"]["lo"]
            hi = bundle["ae_bounds"]["hi"]
            p_anom = np.clip((mse - lo) / (hi - lo + 1e-6), 0.0, 1.0)
    else:
        raw = -bundle["iso_forest"].score_samples(X)
        p_anom = np.clip((raw - np.percentile(raw, 50)) / (np.percentile(raw, 99) + 1e-6), 0.0, 1.0)

    # Pillar 2 (LSTM-FCN)
    if lstm_fcn is not None and "run_id" in df.columns:
        p_lstm = compute_lstm_fcn_probs_for_df(lstm_fcn, df, bundle["features"], bundle["scaler"])
    else:
        p_lstm = p_xgb

    # Unified risk calculation depending on active mode
    if mode == "xgboost":
        risk = p_xgb
    elif mode == "anomaly":
        risk = p_anom
    elif mode == "lstm_fcn":
        risk = p_lstm
    else: # stacked_ensemble
        if getattr(bundle["meta_learner"], "n_features_in_", 3) == 4:
            p_multi_fault = np.clip(1.0 - multi_probs[:, 0], 0.0, 1.0)
            meta_X = np.column_stack([p_xgb, p_lstm, p_anom, p_multi_fault])
        else:
            meta_X = np.column_stack([p_xgb, p_lstm, p_anom])
        cal_params = bundle.get("meta_calibration")
        if cal_params and hasattr(bundle["meta_learner"], "decision_function"):
            raw = bundle["meta_learner"].decision_function(meta_X)
            shift = float(cal_params["shift"])
            scale = float(cal_params.get("scale", 0.75))
            risk = 1.0 / (1.0 + np.exp(-scale * (raw - shift)))
        else:
            risk = bundle["meta_learner"].predict_proba(meta_X)[:, 1]

    # Map multi-class top diagnosis
    top_fault_ids = multi_preds.tolist()
    top_fault_confs = np.max(multi_probs, axis=1).tolist()

    return {
        "risk": risk.astype(float),
        "p_xgb": p_xgb.astype(float),
        "p_lstm": p_lstm.astype(float),
        "p_anom": p_anom.astype(float),
        "fault_class": top_fault_ids,
        "fault_conf": top_fault_confs,
        "multi_probs": multi_probs
    }
