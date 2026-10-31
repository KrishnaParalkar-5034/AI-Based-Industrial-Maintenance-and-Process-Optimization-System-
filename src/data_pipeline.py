"""
Stage 1 & 2 - Data loading and preprocessing.

Data sources (checked in this order):
  1. REAL Tennessee Eastman Process CSVs placed in ./data/ . Any CSV that has the
     columns  faultNumber, simulationRun, sample, xmeas_1..xmeas_41, xmv_1..xmv_11
     (the common Kaggle / Harvard Dataverse export) is used. Several files are concatenated.
  2. Otherwise the Kaggle dataset "ma7bakr/tep-dataset" is downloaded with kagglehub and
     its raw .dat files (d00.dat..d21.dat and d00_te.dat..d21_te.dat, 52 columns, no
     header) are loaded.
  3. Otherwise a TEP-style SYNTHETIC generator is used, so the prototype always runs.
     It simulates pumps / compressor / valve / heat-exchanger style signals with
     gradually developing faults. It is NOT the real TEP data - replace it for results.
"""
import glob
import os
import re

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ROLL_WIN = 10  # rolling window (samples) for engineered features

# Kaggle TEP dataset (raw .dat files from the Braatz / Illinois TEP archive)
KAGGLE_DATASET = "ma7bakr/tep-dataset"
TEP_SENSORS = [f"xmeas_{i}" for i in range(1, 42)] + [f"xmv_{i}" for i in range(1, 12)]

# Human-readable names for the 52 TEP variables (Downs & Vogel, 1993).
TEP_SENSOR_NAMES = [
    # XMEAS 1-22 : flows, pressures, levels and temperatures
    "A Feed Flow", "D Feed Flow", "E Feed Flow", "A and C Feed Flow",
    "Recycle Flow", "Reactor Feed Rate", "Reactor Pressure", "Reactor Level",
    "Reactor Temperature", "Purge Rate", "Separator Temperature", "Separator Level",
    "Separator Pressure", "Separator Underflow", "Stripper Level", "Stripper Pressure",
    "Stripper Underflow", "Stripper Temperature", "Stripper Steam Flow", "Compressor Work",
    "Reactor Cooling Water Outlet Temp", "Condenser Cooling Water Outlet Temp",
    # XMEAS 23-41 : stream composition analysis
    "Feed A Composition", "Feed B Composition", "Feed C Composition", "Feed D Composition",
    "Feed E Composition", "Feed F Composition",
    "Purge A Composition", "Purge B Composition", "Purge C Composition", "Purge D Composition",
    "Purge E Composition", "Purge F Composition", "Purge G Composition", "Purge H Composition",
    "Product D Composition", "Product E Composition", "Product F Composition",
    "Product G Composition", "Product H Composition",
    # XMV 1-11 : manipulated (valve) variables
    "D Feed Valve", "E Feed Valve", "A Feed Valve", "A and C Feed Valve",
    "Compressor Recycle Valve", "Purge Valve", "Separator Liquid Flow Valve",
    "Stripper Liquid Product Valve", "Stripper Steam Valve",
    "Reactor Cooling Water Flow Valve", "Condenser Cooling Water Flow Valve",
]
SENSOR_LABELS = dict(zip(TEP_SENSORS, TEP_SENSOR_NAMES))


def download_kaggle_dataset():
    """Download the TEP dataset with kagglehub and return its local path, else None."""
    try:
        import kagglehub
    except ImportError:
        print("kagglehub not installed. Run: pip install kagglehub")
        return None

    try:
        print("Downloading TEP dataset from Kaggle via kagglehub...")
        path = kagglehub.dataset_download(KAGGLE_DATASET)
        print("Path to dataset files:", path)
        return path
    except Exception as exc:
        print(f"Kaggle download failed ({exc}). Falling back to synthetic data.")
        return None


# name -> (setpoint, noise std)  -- synthetic process variables
SYNTH_VARS = {
    "reactor_temp_C":        (120.4, 0.15),
    "reactor_pressure_kPa":  (2705.0, 8.0),
    "feed_flow_kmolh":       (9.2, 0.12),
    "recycle_flow_kmolh":    (26.9, 0.30),
    "separator_temp_C":      (80.1, 0.25),
    "separator_pressure_kPa": (2633.0, 7.0),
    "stripper_pressure_kPa": (3102.0, 6.0),
    "coolant_flow_m3h":      (41.1, 0.40),
    "hx_diff_pressure_kPa":  (55.0, 0.8),
    "viscosity_index":       (1.00, 0.015),
    "valve_position_pct":    (47.0, 0.50),
    "compressor_work_kW":    (341.0, 2.5),
}

# fault id -> description and signature {variable: shift in noise-std units at full severity}
SYNTH_FAULTS = {
    1: ("Heat-exchanger fouling", {"reactor_temp_C": 5, "coolant_flow_m3h": -4, "hx_diff_pressure_kPa": 4}),
    2: ("Compressor degradation", {"compressor_work_kW": 5, "stripper_pressure_kPa": -4, "recycle_flow_kmolh": -3}),
    3: ("Control valve sticking", {"valve_position_pct": 6, "feed_flow_kmolh": -4, "reactor_pressure_kPa": 3}),
    4: ("Viscosity rise / pump wear", {"viscosity_index": 5, "hx_diff_pressure_kPa": 4, "feed_flow_kmolh": -3}),
}


def generate_synthetic_tep(runs_per_class=30, n_samples=300, onset=120, seed=42):
    """Simulate AR(1) process signals; faults ramp in after `onset` with random severity."""
    rng = np.random.default_rng(seed)
    names = list(SYNTH_VARS)
    frames = []
    for fault in [0] + list(SYNTH_FAULTS):
        for r in range(runs_per_class):
            x = np.zeros((n_samples, len(names)))
            for j, var_name in enumerate(names):
                mu, sd = SYNTH_VARS[var_name]
                e = rng.normal(0, sd, n_samples)
                for t in range(1, n_samples):          # AR(1) process noise
                    x[t, j] = 0.8 * x[t - 1, j] + e[t]
                x[:, j] += mu
            if fault:
                sev = rng.uniform(0.6, 1.0)             # random fault severity
                ramp = np.clip((np.arange(n_samples) - onset) / 80.0, 0, 1)
                for var_name, mag in SYNTH_FAULTS[fault][1].items():
                    x[:, names.index(var_name)] += ramp * mag * sev * SYNTH_VARS[var_name][1] * 1.6
            df = pd.DataFrame(x, columns=names)
            df["sample"] = np.arange(n_samples)
            df["fault_class"] = fault
            df["run_id"] = f"F{fault}_R{r:02d}"
            df["fault_flag"] = ((df["sample"] >= onset) & (fault > 0)).astype(int)
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _assemble(frames):
    """Concatenate raw frames into the common schema used by the rest of the pipeline."""
    raw = pd.concat(frames, ignore_index=True)
    sensors = [c for c in raw.columns if c.startswith(("xmeas_", "xmv_"))]
    out = raw[sensors].copy()
    out["sample"] = raw["sample"].values
    out["fault_class"] = raw["faultNumber"].astype(int).values
    out["run_id"] = ("F" + raw["faultNumber"].astype(int).astype(str) + "_R"
                     + raw["simulationRun"].astype(int).astype(str) + "_" + raw["_source"])
    out["fault_flag"] = ((raw["sample"] >= raw["_onset"]) & (raw["faultNumber"] > 0)).astype(int).values
    # Expose readable names (xmeas_9 -> "Reactor Temperature") to plots and the dashboard
    return out.rename(columns=SENSOR_LABELS)


def _load_dat_file(path):
    """Parse one raw TEP .dat file (52 columns, no header) into the raw frame schema."""
    arr = np.loadtxt(path)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.shape[1] != 52 and arr.shape[0] == 52:   # d00.dat is stored transposed (52 x 500)
        arr = arr.T
    stem = os.path.splitext(os.path.basename(path))[0]          # e.g. "d01_te"
    df = pd.DataFrame(arr, columns=TEP_SENSORS)
    df["sample"] = np.arange(len(df))
    df["faultNumber"] = int(re.match(r"d(\d+)", stem).group(1))
    df["simulationRun"] = 1
    df["_onset"] = 160 if stem.endswith("_te") else 20          # fault introduced after 1 h
    df["_source"] = stem
    return df


def load_kaggle_tep():
    """Download the Kaggle TEP dataset and load its raw .dat files, else None."""
    root = download_kaggle_dataset()
    if not root:
        return None
    files = sorted(glob.glob(os.path.join(root, "**", "d*.dat"), recursive=True))
    if not files:
        return None
    return _assemble([_load_dat_file(p) for p in files])


def load_real_tep():
    """Load real TEP data -> (frame, label), or (None, None).

    Order: local CSVs in ./data (Kaggle/Harvard header format), then the Kaggle
    "ma7bakr/tep-dataset" raw .dat archive downloaded with kagglehub.
    """
    frames = []
    for path in glob.glob(os.path.join(DATA_DIR, "*.csv")):
        head = pd.read_csv(path, nrows=2)
        if {"faultNumber", "simulationRun", "sample"}.issubset(head.columns):
            chunk = pd.read_csv(path)
            # Per-file onset: training files (<=500 samples) -> 20, testing files -> 160
            chunk["_onset"] = 20 if chunk["sample"].max() <= 500 else 160
            chunk["_source"] = os.path.basename(path)
            frames.append(chunk)
    if frames:
        return _assemble(frames), "Local TEP CSV (./data)"

    df = load_kaggle_tep()
    return (df, f"Kaggle TEP dataset ({KAGGLE_DATASET})") if df is not None else (None, None)


def clean(df, sensors):
    """Interpolate gaps inside each run, then fall back to column medians."""
    df = df.sort_values(["run_id", "sample"]).reset_index(drop=True)
    df[sensors] = df.groupby("run_id")[sensors].transform(lambda s: s.interpolate(limit_direction="both"))
    df[sensors] = df[sensors].fillna(df[sensors].median())
    return df


def engineer_features(df, sensors, win=ROLL_WIN):
    """Add rolling mean / std per run (captures trends and growing variability)."""
    g = df.groupby("run_id")[sensors]
    rm = g.transform(lambda s: s.rolling(win, min_periods=1).mean()).add_suffix("_rmean")
    rs = g.transform(lambda s: s.rolling(win, min_periods=2).std()).fillna(0).add_suffix("_rstd")
    return pd.concat([df, rm, rs], axis=1)


def build_dataset(seed=42, test_size=0.2):
    """Full pipeline -> dict with train/test frames, scaled matrices and the fitted scaler."""
    df, source = load_real_tep()
    if df is None:
        df = generate_synthetic_tep(seed=seed)
        source = "Synthetic TEP-style data"
    sensors = [c for c in df.columns if c not in ("sample", "fault_class", "run_id", "fault_flag")]
    df = clean(df, sensors)
    df = engineer_features(df, sensors)
    feats = [c for c in df.columns if c.endswith(("_rmean", "_rstd"))] + sensors

    # 80/20 split by simulation RUN (stratified by fault class) so no time-leakage between sets
    rng = np.random.default_rng(seed)
    runs = df.groupby("run_id")["fault_class"].first()
    test_runs = []
    for _, ids in runs.groupby(runs).groups.items():
        ids = np.array(list(ids))
        rng.shuffle(ids)
        test_runs += list(ids[: max(1, int(round(len(ids) * test_size)))])
    is_test = df["run_id"].isin(test_runs)
    train, test = df[~is_test].reset_index(drop=True), df[is_test].reset_index(drop=True)

    scaler = StandardScaler().fit(train[feats])
    normal = train[train["fault_flag"] == 0]
    return dict(
        source=source, sensors=sensors, features=feats, train=train, test=test,
        X_train=scaler.transform(train[feats]), X_test=scaler.transform(test[feats]),
        y_train=train["fault_flag"].values, y_test=test["fault_flag"].values,
        scaler=scaler,
        normal_mean=normal[sensors].mean(), normal_std=normal[sensors].std().replace(0, 1e-9),
    )
