"""Quick look at the dataset: shape, missing values, class balance, example signals."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data_pipeline import build_dataset

if __name__ == "__main__":
    ds = build_dataset()
    tr, te = ds["train"], ds["test"]
    print(f"Source: {ds['source']}")
    print(f"Train rows: {len(tr)} | Test rows: {len(te)} | Sensors: {len(ds['sensors'])} | Features: {len(ds['features'])}")
    print("\nRuns per fault class (train/test):")
    print(tr.groupby('fault_class')['run_id'].nunique().to_frame('train').join(
        te.groupby('fault_class')['run_id'].nunique().to_frame('test')))
    print("\nFailure-flag balance (train):\n", tr["fault_flag"].value_counts(normalize=True).round(3))
    print("\nSensor summary:\n", tr[ds["sensors"]].describe().T[["mean", "std", "min", "max"]].round(2))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cols = ds["sensors"][:4]
    normal = tr[tr.fault_class == 0].run_id.iloc[0]
    fault = tr[tr.fault_class > 0].run_id.iloc[0]
    fig, ax = plt.subplots(len(cols), 1, figsize=(9, 7), sharex=True)
    for a, c in zip(ax, cols):
        for rid, lab in ((normal, "normal"), (fault, "faulty")):
            d = tr[tr.run_id == rid]
            a.plot(d["sample"], d[c], label=lab)
        a.set_ylabel(c, fontsize=7)
    ax[0].legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "explore_signals.png"), dpi=120)
    print(f"\nSaved {os.path.join(OUTPUT_DIR, 'explore_signals.png')}")
