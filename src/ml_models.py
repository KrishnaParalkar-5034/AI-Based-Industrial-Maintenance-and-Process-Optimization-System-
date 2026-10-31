"""
Stage 3 - ML engine: supervised failure classifiers + unsupervised anomaly detector.
Metrics reported on the held-out test set: Precision, Recall, F1.
"""
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

try:
    from xgboost import XGBClassifier
except ImportError:  # optional dependency
    XGBClassifier = None

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
BUNDLE_PATH = os.path.join(MODEL_DIR, "bundle.joblib")


def _metrics(y, pred):
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return dict(precision=precision_score(y, pred, zero_division=0),
                recall=recall_score(y, pred, zero_division=0),
                f1=f1_score(y, pred, zero_division=0),
                tp=int(tp), fp=int(fp), fn=int(fn), tn=int(tn))


def _importances(model, features):
    """Rank features by importance (tree models) or |coefficient| (linear models)."""
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
    elif hasattr(model, "coef_"):
        imp = np.abs(np.asarray(model.coef_)).ravel()
    else:
        return None
    return pd.Series(imp, index=features).sort_values(ascending=False)


def train_models(ds, seed=42):
    Xtr, ytr, Xte, yte = ds["X_train"], ds["y_train"], ds["X_test"], ds["y_test"]

    candidates = {
        "Random Forest": RandomForestClassifier(n_estimators=200, max_depth=14, class_weight="balanced",
                                                n_jobs=-1, random_state=seed),
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
    }
    if XGBClassifier is not None:
        pos_w = (ytr == 0).sum() / max(1, (ytr == 1).sum())
        candidates["XGBoost"] = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.1,
                                              scale_pos_weight=pos_w, eval_metric="logloss", random_state=seed)

    results, fitted = {}, {}
    for name, model in candidates.items():
        model.fit(Xtr, ytr)
        results[name] = _metrics(yte, model.predict(Xte))
        fitted[name] = model

    # Unsupervised anomaly detector: learns NORMAL behaviour only
    iso = IsolationForest(n_estimators=200, contamination=0.01, random_state=seed, n_jobs=-1)
    iso.fit(Xtr[ytr == 0])
    raw_tr = -iso.score_samples(Xtr[ytr == 0])
    lo, hi = np.percentile(raw_tr, 50), np.percentile(raw_tr, 99.5)
    iso_pred = (-iso.score_samples(Xte) > hi).astype(int)
    results["Isolation Forest (anomaly)"] = _metrics(yte, iso_pred)

    # Optional deep-learning baseline: LSTM over sliding windows. Only the metrics are
    # stored in the bundle, so loading it never requires torch to be installed.
    try:
        from .sequence_model import train_lstm
        lstm = train_lstm(ds, seed=seed)
    except Exception as exc:            # keep the pipeline running if torch / training fails
        print(f"[ml_models] LSTM skipped: {exc}")
        lstm = None
    if lstm is not None:
        results["LSTM (sequence)"] = lstm["metrics"]

    best = max(fitted, key=lambda n: results[n]["f1"])
    bundle = dict(classifier=fitted[best], classifier_name=best, iso=iso, iso_lo=lo, iso_hi=hi,
                  scaler=ds["scaler"], features=ds["features"], sensors=ds["sensors"],
                  normal_mean=ds["normal_mean"], normal_std=ds["normal_std"],
                  metrics=results, source=ds["source"], test=ds["test"],
                  importances=_importances(fitted[best], ds["features"]))
    return bundle


def save_bundle(bundle):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(bundle, BUNDLE_PATH)
    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump(bundle["metrics"], f, indent=2)


def load_bundle():
    return joblib.load(BUNDLE_PATH) if os.path.exists(BUNDLE_PATH) else None


def score_frame(bundle, df):
    """Return (failure_probability, anomaly_score in 0..1) for every row of df."""
    X = bundle["scaler"].transform(df[bundle["features"]])
    proba = bundle["classifier"].predict_proba(X)
    # Guard: if only one class was seen during training, predict_proba has a single column
    if proba.shape[1] < 2:
        p_fail = (np.ones(len(X)) if bundle["classifier"].classes_[0] == 1
                  else np.zeros(len(X)))
    else:
        p_fail = proba[:, 1]
    raw = -bundle["iso"].score_samples(X)
    anom = np.clip((raw - bundle["iso_lo"]) / (bundle["iso_hi"] - bundle["iso_lo"] + 1e-9), 0, 1)
    return p_fail, anom
