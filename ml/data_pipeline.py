"""
Causal Data Ingestion, Cleaning & Multi-Scale Feature Engineering Pipeline for TEP.
Strict zero-leakage causal forward-filling and run-stratified splitting.
"""
import glob
import os
import re
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .config import (
    SENSOR_LABELS,
    TEP_FAULT_DEFINITIONS,
    TEP_SENSORS,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
KAGGLE_DATASET = "ma7bakr/tep-dataset"

# Multi-scale causal feature windows
SHORT_WIN = 10
MED_WIN = 30


def download_kaggle_tep() -> Optional[str]:
    """Download the TEP dataset with kagglehub and return local root path."""
    try:
        import kagglehub
    except ImportError:
        print("[data_pipeline] kagglehub not installed. Run: pip install kagglehub")
        return None

    try:
        print("[data_pipeline] Checking/downloading TEP dataset from Kaggle via kagglehub...")
        path = kagglehub.dataset_download(KAGGLE_DATASET)
        print("[data_pipeline] Kaggle dataset path:", path)
        return path
    except Exception as exc:
        print(f"[data_pipeline] Kaggle download failed ({exc}).")
        return None


def generate_synthetic_tep_21(
    runs_per_fault: int = 10,
    n_samples: int = 300,
    onset: int = 100,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic 52-variable TEP telemetry covering all 21 fault modes + normal.
    Uses coupled AR(1) process dynamics with physical disturbance profiles.
    """
    rng = np.random.default_rng(seed)
    n_sensors = len(TEP_SENSORS)
    frames = []

    # Realistic nominal baselines and noise std for standard 52 variables
    base_means = rng.uniform(10.0, 150.0, size=n_sensors).astype(np.float32)
    # Give pressure, flow, and temperature realistic engineering orders of magnitude
    base_means[6] = 2705.0   # Reactor pressure
    base_means[7] = 65.0     # Reactor level ~65%
    base_means[8] = 120.4    # Reactor temp
    base_means[11] = 50.0    # Separator level ~50%
    base_means[14] = 50.0    # Stripper level ~50%
    base_means[17] = 65.8    # Stripper temp ~65.8 C
    base_means[19] = 341.0   # Compressor work
    base_means[41:52] = 50.0 # Valves (%)
    base_stds = np.maximum(base_means * 0.02, 0.25).astype(np.float32)

    all_faults = list(range(22)) # 0: Normal, 1..21: Faults

    for fault in all_faults:
        # Give normal operating baseline higher run representation for healthy industrial class balance
        n_runs = runs_per_fault * 3 if fault == 0 else runs_per_fault
        for r in range(n_runs):
            x = np.zeros((n_samples, n_sensors), dtype=np.float32)
            e = rng.normal(0, base_stds, size=(n_samples, n_sensors)).astype(np.float32)

            for t in range(n_samples):
                if t == 0:
                    x[t] = base_means + e[t]
                else:
                    # AR(1) persistence
                    x[t] = base_means + 0.82 * (x[t - 1] - base_means) + e[t]

            # Inject fault physics after onset
            if fault > 0:
                sev = float(rng.uniform(0.75, 1.25))
                ramp = np.clip((np.arange(n_samples) - onset) / 50.0, 0.0, 1.0)[:, None]

                # Disturbance profiles tailored to fault index
                affected_cols = [(fault * 2 + i) % n_sensors for i in range(3)]
                signs = np.array([1.0, -0.8, 0.6], dtype=np.float32)

                # Special cases for key unit disturbances
                if fault in [4, 11, 14]: # Reactor cooling water faults
                    affected_cols += [8, 20, 50] # Reactor temp, cooling water temp, valve
                    signs = np.concatenate([signs, np.array([1.2, -1.0, 1.5], dtype=np.float32)])
                elif fault in [5, 12, 15]: # Condenser cooling water faults
                    affected_cols += [21, 51] # Condenser temp, condenser valve
                    signs = np.concatenate([signs, np.array([-1.1, 1.3], dtype=np.float32)])
                elif fault in [1, 2, 6, 7]: # Feed system faults
                    affected_cols += [0, 1, 2, 3, 42]
                    signs = np.concatenate([signs, np.array([-1.2, 1.0, -0.9, 0.8, 1.1], dtype=np.float32)])
                elif fault in [16, 17, 18, 19]: # Fouling / scaling drift
                    affected_cols += [10, 17, 18] # Separator & Stripper temps/flows
                    signs = np.concatenate([signs, np.array([0.9, -0.7, 1.0], dtype=np.float32)])

                affected_cols = np.array(affected_cols[:len(signs)], dtype=int) % n_sensors
                # Realistic TEP physical step disturbance (5.2x noise; 2.2x for subtle low-SNR faults 3, 9, 15)
                mag_factor = 2.2 if fault in [3, 9, 15] else 5.2
                for idx_col, sign in zip(affected_cols, signs):
                    magnitude = sign * sev * base_stds[idx_col] * mag_factor
                    x[:, idx_col] += (ramp[:, 0] * magnitude).astype(np.float32)

            # Clamp liquid tank levels (Reactor, Separator, Stripper: indices 7, 11, 14) to physical limits
            x[:, [7, 11, 14]] = np.clip(x[:, [7, 11, 14]], 10.0, 95.0)

            df = pd.DataFrame(x, columns=TEP_SENSORS)
            df["sample"] = np.arange(n_samples, dtype=np.int32)
            df["fault_class"] = int(fault)
            df["run_id"] = f"F{fault:02d}_R{r:02d}"
            df["fault_flag"] = ((df["sample"] >= onset) & (fault > 0)).astype(np.int32)
            df["_onset"] = int(onset)
            frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    return combined.rename(columns=SENSOR_LABELS)


def _load_dat_file(path: str) -> pd.DataFrame:
    """Parse one raw TEP .dat file (52 columns, no header) into the standardized frame."""
    arr = np.loadtxt(path, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.shape[1] != 52 and arr.shape[0] == 52:
        arr = arr.T
    stem = os.path.splitext(os.path.basename(path))[0]
    df = pd.DataFrame(arr, columns=TEP_SENSORS)
    df["sample"] = np.arange(len(df), dtype=np.int32)
    m = re.match(r"d(\d+)", stem)
    df["faultNumber"] = int(m.group(1)) if m else 0
    df["simulationRun"] = 1
    df["_onset"] = 160 if stem.endswith("_te") else 20
    df["_source"] = stem
    return df


def _assemble_raw_frames(frames: List[pd.DataFrame]) -> pd.DataFrame:
    """Unify raw frames into a common schema with readable sensor names."""
    raw = pd.concat(frames, ignore_index=True)
    sensors = [c for c in raw.columns if c.startswith(("xmeas_", "xmv_"))]
    out = raw[sensors].copy().astype(np.float32)
    out["sample"] = raw["sample"].values.astype(np.int32)
    out["fault_class"] = raw["faultNumber"].astype(int).values
    out["run_id"] = (
        "F" + raw["faultNumber"].astype(int).astype(str) + "_R"
        + raw["simulationRun"].astype(int).astype(str) + "_" + raw["_source"].astype(str)
    )
    out["fault_flag"] = ((raw["sample"] >= raw["_onset"]) & (raw["faultNumber"] > 0)).astype(np.int32).values
    out["_onset"] = raw["_onset"].values
    return out.rename(columns=SENSOR_LABELS)


def load_raw_dataset(max_runs_per_fault: int = 40, dataset_type: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    """
    Load raw TEP data in order:
      1. Local CSVs in ./data (Downs & Vogel format with columns faultNumber, simulationRun, sample, xmeas_*, xmv_*)
      2. Kaggle tep-dataset raw .dat files
      3. 21-class synthetic fallback simulation
    Supports explicit dataset_type: "kaggle_dat", "csv", "synthetic".
    """
    if dataset_type == "synthetic":
        print("[data_pipeline] Explicitly generating 21-class Synthetic TEP Simulation...")
        syn_df = generate_synthetic_tep_21(runs_per_fault=min(max_runs_per_fault, 12))
        return syn_df, "Synthetic TEP-21 Simulation"

    if dataset_type in [None, "csv"]:
        frames = []
        csv_paths = glob.glob(os.path.join(DATA_DIR, "*.csv"))
        if csv_paths:
            for path in sorted(csv_paths):
                head = pd.read_csv(path, nrows=2)
                if {"faultNumber", "simulationRun", "sample"}.issubset(head.columns):
                    chunk = pd.read_csv(path)
                    if max_runs_per_fault:
                        chunk = chunk.groupby("faultNumber").apply(
                            lambda g: g[g["simulationRun"] <= max_runs_per_fault]
                        ).reset_index(drop=True)
                    chunk["_onset"] = 20 if chunk["sample"].max() <= 500 else 160
                    chunk["_source"] = os.path.basename(path)
                    frames.append(chunk)
            if frames:
                return _assemble_raw_frames(frames), "Local TEP CSV Files"
            elif dataset_type == "csv":
                raise FileNotFoundError(f"No valid TEP CSV files found in {DATA_DIR}")

    # Try Kaggle
    if dataset_type in [None, "kaggle_dat"]:
        kaggle_root = download_kaggle_tep()
        if kaggle_root:
            dat_files = sorted(glob.glob(os.path.join(kaggle_root, "**", "d*.dat"), recursive=True))
            if dat_files:
                dat_frames = [_load_dat_file(f) for f in dat_files]
                return _assemble_raw_frames(dat_frames), f"Kaggle TEP Dataset ({KAGGLE_DATASET})"
            elif dataset_type == "kaggle_dat":
                raise FileNotFoundError("Kaggle download completed but no .dat files found.")
        elif dataset_type == "kaggle_dat":
            raise RuntimeError("Failed to download Kaggle TEP dataset.")

    # Fallback to realistic synthetic TEP generator
    print("[data_pipeline] Using 21-class Synthetic TEP Simulation generator...")
    syn_df = generate_synthetic_tep_21(runs_per_fault=min(max_runs_per_fault, 12))
    return syn_df, "Synthetic TEP-21 Simulation"


def clean_causal(df: pd.DataFrame, sensors: List[str], normal_medians: Optional[pd.Series] = None) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Strictly causal cleaning:
      - Sort by [run_id, sample].
      - Causal forward-fill (ffill) within each run.
      - Any leading NaNs at t=0 are filled by baseline normal medians.
    Zero future-lookahead or bidirectional interpolation.
    """
    df = df.sort_values(["run_id", "sample"]).reset_index(drop=True)
    df[sensors] = df.groupby("run_id")[sensors].transform(lambda s: s.ffill())

    if normal_medians is None:
        normal_mask = (df["fault_flag"] == 0)
        normal_medians = df.loc[normal_mask, sensors].median()

    df[sensors] = df[sensors].fillna(normal_medians).astype(np.float32)
    return df, normal_medians


def compute_causal_features(df: pd.DataFrame, sensors: List[str], w_short: int = SHORT_WIN, w_med: int = MED_WIN) -> pd.DataFrame:
    """
    Compute multi-scale causal rolling features per simulationRun:
      - Short window (W=10): rolling mean, rolling std, first-order delta (x_t - x_{t-1}).
      - Medium window (W=30): rolling mean, rolling std, trend slope (mean_10 - mean_30).
    """
    g = df.groupby("run_id")[sensors]

    # Short scale features
    rm_short = g.transform(lambda s: s.rolling(w_short, min_periods=1).mean()).astype(np.float32).add_suffix("_m10")
    rs_short = g.transform(lambda s: s.rolling(w_short, min_periods=2).std()).fillna(0.0).astype(np.float32).add_suffix("_s10")
    delta_1 = g.transform(lambda s: s.diff().fillna(0.0)).astype(np.float32).add_suffix("_d1")

    # Medium scale features
    rm_med = g.transform(lambda s: s.rolling(w_med, min_periods=1).mean()).astype(np.float32).add_suffix("_m30")
    rs_med = g.transform(lambda s: s.rolling(w_med, min_periods=2).std()).fillna(0.0).astype(np.float32).add_suffix("_s30")

    # Trend slope: short mean minus medium mean
    trend = (rm_short.values - rm_med.values).astype(np.float32)
    trend_df = pd.DataFrame(trend, columns=[f"{s}_slope" for s in sensors], index=df.index)

    return pd.concat([df, rm_short, rs_short, delta_1, rm_med, rs_med, trend_df], axis=1)


def build_dataset(
    max_runs_per_fault: int = 40,
    test_size: float = 0.20,
    val_size: float = 0.10,
    seed: int = 42,
    dataset_type: Optional[str] = None
) -> Dict[str, Union[pd.DataFrame, np.ndarray, StandardScaler, pd.Series, List[str], str]]:
    """
    Full zero-leakage pipeline:
      1. Load raw data.
      2. Run-stratified 3-way split (Train / Val / Test) with zero run overlap.
      3. Causal clean using training-set normal medians.
      4. Multi-scale causal feature engineering.
      5. Fit StandardScaler strictly on Train split.
    """
    raw_df, source = load_raw_dataset(max_runs_per_fault=max_runs_per_fault, dataset_type=dataset_type)
    sensors = [c for c in raw_df.columns if c not in ("sample", "fault_class", "run_id", "fault_flag", "_onset")]

    # Determine if dataset has dedicated held-out test runs (e.g. Kaggle TEP d*_te files)
    is_te_series = raw_df["run_id"].str.contains("_te")
    has_te_runs = bool(is_te_series.any() and (~is_te_series).any())

    if has_te_runs:
        # Canonical benchmark split:
        # All *_te runs are reserved strictly for held-out evaluation (all 22 fault classes)
        # Training runs are partitioned temporally (first 75% train, last 25% val)
        test_mask = is_te_series.values
        train_mask = ((~is_te_series) & (raw_df["sample"] < 375)).values
        val_mask = ((~is_te_series) & (raw_df["sample"] >= 375)).values

        train_raw = raw_df[train_mask].copy()
        normal_medians = train_raw.loc[train_raw["fault_flag"] == 0, sensors].median()

        cleaned_df, _ = clean_causal(raw_df, sensors, normal_medians=normal_medians)
        feat_df = compute_causal_features(cleaned_df, sensors)

        meta_cols = ["sample", "fault_class", "run_id", "fault_flag", "_onset"]
        feature_cols = [c for c in feat_df.columns if c not in meta_cols]

        train = feat_df[train_mask].reset_index(drop=True)
        val = feat_df[val_mask].copy().reset_index(drop=True)
        val["run_id"] = val["run_id"] + "_val"
        test = feat_df[test_mask].reset_index(drop=True)
    else:
        # Multi-run split by simulationRun (stratified by fault class) to ensure zero time-leakage
        runs = raw_df.groupby("run_id")["fault_class"].first()
        rng = np.random.default_rng(seed)

        train_runs, val_runs, test_runs = [], [], []
        for f_class, ids in runs.groupby(runs).groups.items():
            arr = np.array(list(ids))
            rng.shuffle(arr)
            n_tot = len(arr)
            n_test = max(1, int(round(n_tot * test_size)))
            n_val = max(1, int(round(n_tot * val_size)))
            test_runs.extend(arr[:n_test])
            val_runs.extend(arr[n_test:n_test + n_val])
            train_runs.extend(arr[n_test + n_val:])

        # Fallback guard if too few runs
        if not train_runs:
            train_runs = test_runs[:len(test_runs)//2]
            test_runs = test_runs[len(test_runs)//2:]

        # Causal clean using normal rows from train set
        train_raw = raw_df[raw_df["run_id"].isin(train_runs)].copy()
        normal_medians = train_raw.loc[train_raw["fault_flag"] == 0, sensors].median()

        cleaned_df, _ = clean_causal(raw_df, sensors, normal_medians=normal_medians)
        feat_df = compute_causal_features(cleaned_df, sensors)

        meta_cols = ["sample", "fault_class", "run_id", "fault_flag", "_onset"]
        feature_cols = [c for c in feat_df.columns if c not in meta_cols]

        train = feat_df[feat_df["run_id"].isin(train_runs)].reset_index(drop=True)
        val = feat_df[feat_df["run_id"].isin(val_runs)].reset_index(drop=True)
        test = feat_df[feat_df["run_id"].isin(test_runs)].reset_index(drop=True)

    scaler = StandardScaler().fit(train[feature_cols].values.astype(np.float32))

    X_train = scaler.transform(train[feature_cols].values.astype(np.float32)).astype(np.float32)
    X_val = scaler.transform(val[feature_cols].values.astype(np.float32)).astype(np.float32)
    X_test = scaler.transform(test[feature_cols].values.astype(np.float32)).astype(np.float32)

    normal_train = train[train["fault_flag"] == 0]
    normal_mean = normal_train[sensors].mean().astype(np.float32)
    normal_std = normal_train[sensors].std().replace(0, 1e-6).astype(np.float32)

    return dict(
        source=source,
        sensors=sensors,
        features=feature_cols,
        train=train,
        val=val,
        test=test,
        X_train=X_train,
        X_val=X_val,
        X_test=X_test,
        y_train_bin=train["fault_flag"].values.astype(np.int32),
        y_val_bin=val["fault_flag"].values.astype(np.int32),
        y_test_bin=test["fault_flag"].values.astype(np.int32),
        y_train_multi=train["fault_class"].values.astype(np.int32),
        y_val_multi=val["fault_class"].values.astype(np.int32),
        y_test_multi=test["fault_class"].values.astype(np.int32),
        scaler=scaler,
        normal_mean=normal_mean,
        normal_std=normal_std,
    )
