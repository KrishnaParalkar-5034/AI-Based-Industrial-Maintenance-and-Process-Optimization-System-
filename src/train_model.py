"""Train, evaluate (Precision / Recall / F1) and save the models used by the dashboard."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

from src.data_pipeline import build_dataset
from src.ml_models import save_bundle, train_models

if __name__ == "__main__":
    ds = build_dataset()
    print(f"Data source: {ds['source']} | train {ds['X_train'].shape} | test {ds['X_test'].shape}")
    bundle = train_models(ds)
    save_bundle(bundle)
    table = pd.DataFrame(bundle["metrics"]).T[["precision", "recall", "f1", "tp", "fp", "fn", "tn"]]
    print("\nHeld-out test-set results:\n", table.round(3))
    print(f"\nBest classifier (by F1): {bundle['classifier_name']}")
    print("Saved models/bundle.joblib and models/metrics.json")
