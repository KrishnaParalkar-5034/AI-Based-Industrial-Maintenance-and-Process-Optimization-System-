"""
Google Colab / On-Prem Production Training Orchestrator for TEP Predictive Maintenance.
Trains 3 heterogeneous pillars + 21-class fault isolator + stacking meta-learner.
Produces portable production artifacts ready for local/Docker inference.

Usage:
  python -m ml.train_colab --dataset synthetic --max-runs-per-fault 15 --output-dir ./models
"""
import argparse
import json
import os
import shutil
import sys
import time
import zipfile
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
import torch

from .config import LOW_SNR_FAULTS, TEP_FAULT_DEFINITIONS
from .data_pipeline import build_dataset
from .models import compute_lstm_fcn_probs_for_df, train_all_models


def detect_environment() -> Dict[str, Any]:
    """Detect hardware accelerator, VRAM, and runtime environment."""
    info = {
        "is_colab": "google.colab" in sys.modules,
        "cuda_available": torch.cuda.is_available(),
        "device_name": "CPU",
        "vram_gb": 0.0,
    }
    if info["cuda_available"]:
        info["device_name"] = torch.cuda.get_device_name(0)
        info["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    return info


def early_warning_audit(bundle: Dict[str, Any], autoencoder: Any, lstm_fcn: Any) -> Dict[str, Any]:
    """Audit early-warning detection delay and false-alarm performance on held-out test runs."""
    test_df = bundle["test"].copy()
    scaler = bundle["scaler"]
    features = bundle["features"]
    runs = test_df.groupby("run_id")

    audit_records = []
    sample_interval_min = 3.0

    total_d00_samples = 0
    d00_fp_samples = 0
    total_pre_onset_samples = 0
    pre_fp_samples = 0

    for run_id, run in runs:
        run = run.sort_values("sample").reset_index(drop=True)
        fault_class = int(run["fault_class"].iloc[0])
        onset_series = run["sample"][run["fault_flag"] == 1]
        actual_onset = int(onset_series.iloc[0]) if len(onset_series) > 0 else None

        X = scaler.transform(run[features].values.astype(np.float32))
        cal_xgb = bundle.get("xgb_calibrated", bundle["xgb_binary"])
        p_xgb = cal_xgb.predict_proba(X)[:, 1]
        p_lstm = compute_lstm_fcn_probs_for_df(lstm_fcn, run, features, scaler)

        # Score with Autoencoder
        with torch.no_grad():
            xt = torch.from_numpy(X).float()
            if torch.cuda.is_available():
                xt = xt.cuda()
                autoencoder = autoencoder.cuda()
            mse = torch.mean((autoencoder(xt) - xt)**2, dim=-1).cpu().numpy()
            lo = bundle["ae_bounds"]["lo"]
            hi = bundle["ae_bounds"]["hi"]
            p_anom = np.clip((mse - lo) / (hi - lo + 1e-6), 0.0, 1.0)

        if getattr(bundle["meta_learner"], "n_features_in_", 3) == 4 and "xgb_multi" in bundle:
            p_multi = np.clip(1.0 - bundle["xgb_multi"].predict_proba(X)[:, 0], 0.0, 1.0)
            meta_X = np.column_stack([p_xgb, p_lstm, p_anom, p_multi])
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

        # Explicit FPR tracking at threshold 0.50
        if fault_class == 0:
            total_d00_samples += len(risk)
            d00_fp_samples += int((risk >= 0.50).sum())
        elif actual_onset is not None:
            pre_slice = risk[:actual_onset]
            total_pre_onset_samples += len(pre_slice)
            pre_fp_samples += int((pre_slice >= 0.50).sum())

        # Simple moving average to prevent chatter
        smoothed_risk = pd.Series(risk).rolling(5, min_periods=1).mean().values

        # Check pre-onset false alarm on this run
        pre_onset_mask = (run["sample"].values < actual_onset) if actual_onset is not None else np.ones(len(run), dtype=bool)
        pre_alerts = np.where((smoothed_risk >= 0.70) & pre_onset_mask)[0]
        has_pre_onset_alarm = len(pre_alerts) > 0

        # Post-onset detection delay (ANSI/ISA-18.2 detection standard)
        post_onset_mask = (run["sample"].values >= actual_onset) if actual_onset is not None else np.zeros(len(run), dtype=bool)
        post_alerts = np.where((smoothed_risk >= 0.70) & post_onset_mask)[0]
        first_post_alert = int(run["sample"].iloc[post_alerts[0]]) if len(post_alerts) > 0 else None

        delay = None
        if actual_onset is not None and first_post_alert is not None:
            delay = first_post_alert - actual_onset

        audit_records.append({
            "run_id": run_id,
            "fault_class": fault_class,
            "is_low_snr": fault_class in LOW_SNR_FAULTS,
            "onset": actual_onset,
            "first_alert": first_post_alert,
            "delay_samples": delay,
            "delay_minutes": delay * sample_interval_min if delay is not None else None,
            "false_alarm_normal": (len(pre_alerts) > 0 and fault_class == 0),
            "false_alarm_pre_onset": has_pre_onset_alarm if fault_class > 0 else False,
        })

    audit_df = pd.DataFrame(audit_records)
    faulty_runs = audit_df[audit_df["fault_class"] > 0]
    detected_runs = faulty_runs[faulty_runs["delay_samples"].notna() & (faulty_runs["delay_samples"] >= 0)]
    normal_runs = audit_df[audit_df["fault_class"] == 0]

    # Detectable faults breakdown (excluding low-SNR faults 3, 9, 15)
    det_faults = faulty_runs[~faulty_runs["is_low_snr"]]
    det_detected = det_faults[det_faults["delay_samples"].notna() & (det_faults["delay_samples"] >= 0)]
    det_rate_pct = round(100.0 * (len(det_detected) / max(1, len(det_faults))), 1)

    median_delay = float(det_detected["delay_samples"].median()) if len(det_detected) > 0 else (
        float(detected_runs["delay_samples"].median()) if len(detected_runs) > 0 else None
    )

    d00_fpr_pct = round(100.0 * (d00_fp_samples / max(1, total_d00_samples)), 2)
    pre_fpr_pct = round(100.0 * (pre_fp_samples / max(1, total_pre_onset_samples)), 2)

    return {
        "total_test_runs": len(audit_df),
        "faulty_test_runs": len(faulty_runs),
        "detected_faults": len(detected_runs),
        "missed_faults": len(faulty_runs) - len(detected_runs),
        "detection_rate_pct": round(100.0 * (len(detected_runs) / max(1, len(faulty_runs))), 1),
        "detectable_faults_total": len(det_faults),
        "detectable_faults_detected": len(det_detected),
        "detectable_detection_rate_pct": det_rate_pct,
        "median_detection_delay_samples": median_delay,
        "median_detection_delay_minutes": round(median_delay * sample_interval_min, 1) if median_delay else None,
        "pre_onset_false_alarms": int(faulty_runs["false_alarm_pre_onset"].sum()),
        "normal_run_false_alarms": int(normal_runs["false_alarm_normal"].sum()),
        "normal_run_fpr_pct": d00_fpr_pct,
        "pre_onset_fpr_pct": pre_fpr_pct,
    }


def main():
    parser = argparse.ArgumentParser(description="TEP Production Model Trainer (Colab/Local)")
    parser.add_argument("--dataset", type=str, default="synthetic", choices=["synthetic", "csv", "kaggle_dat"])
    parser.add_argument("--max-runs-per-fault", type=int, default=15, help="Cap runs per fault class to manage RAM")
    parser.add_argument("--output-dir", type=str, default="./models", help="Output path for artifacts")
    parser.add_argument("--epochs", type=int, default=8, help="Epochs for deep learning models")
    args = parser.parse_args()

    t0 = time.time()
    env = detect_environment()
    print("=" * 70)
    print("🏭 TEP PREDICTIVE MAINTENANCE: 3-PILLAR HETEROGENEOUS TRAINING")
    print(f"Runtime: {'Google Colab' if env['is_colab'] else 'Local / Cloud Instance'}")
    print(f"Device:  {env['device_name']} (VRAM: {env['vram_gb']} GB)")
    print(f"Dataset: {args.dataset} | Max runs/class: {args.max_runs_per_fault}")
    print("=" * 70)

    # 1. Build zero-leakage dataset
    ds = build_dataset(max_runs_per_fault=args.max_runs_per_fault, dataset_type=args.dataset)
    print(f"[pipeline] Dataset loaded from '{ds['source']}'")
    print(f"[pipeline] Train shape: {ds['X_train'].shape} | Val: {ds['X_val'].shape} | Test: {ds['X_test'].shape}")
    print(f"[pipeline] Features engineered: {len(ds['features'])} across {len(ds['sensors'])} sensors")

    # Determine dataset origin metadata
    source_str = ds.get("source", "").lower()
    if "kaggle" in source_str or args.dataset == "kaggle_dat":
        dataset_origin = "real_tep_kaggle_dat"
    elif "csv" in source_str or args.dataset == "csv":
        dataset_origin = "real_tep_csv"
    else:
        dataset_origin = "synthetic_ar1"

    # 2. Train 3-pillar ensemble
    results = train_all_models(ds)
    bundle = results["bundle"]
    lstm_fcn = results["lstm_fcn"]
    autoencoder = results["autoencoder"]
    metrics = results["metrics"]

    bundle["dataset_origin"] = dataset_origin
    metrics["dataset_origin"] = dataset_origin

    # 3. Perform Early-Warning Detection Delay Audit
    print("[audit] Running early-warning detection delay audit...")
    audit = early_warning_audit(bundle, autoencoder, lstm_fcn)
    metrics["Early Warning Audit (Detection Delay)"] = audit

    # Print summary benchmark table
    print("\n" + "=" * 70)
    print("📊 BENCHMARK METRICS SUMMARY (Held-Out Test Set)")
    print("=" * 70)
    for model_name, m in metrics.items():
        if isinstance(m, dict) and "f1" in m:
            print(f"  • {model_name:<36} | F1: {m['f1']:.4f} | Recall: {m['recall']:.4f} | Precision: {m['precision']:.4f} | ROC-AUC: {m.get('roc_auc', 0.5):.4f}")
        elif isinstance(m, dict) and "macro_f1" in m:
            print(f"  • {model_name:<36} | Macro F1: {m['macro_f1']:.4f} | Weighted F1: {m['weighted_f1']:.4f}")

    print("\n⏱️ EARLY-WARNING DETECTION DELAY AUDIT:")
    print(f"  • Detectable Fault Detection Rate: {audit.get('detectable_detection_rate_pct', audit['detection_rate_pct'])}% ({audit.get('detectable_faults_detected', audit['detected_faults'])}/{audit.get('detectable_faults_total', audit['faulty_test_runs'])} runs)")
    print(f"  • Overall Fault Detection Rate:    {audit['detection_rate_pct']}% ({audit['detected_faults']}/{audit['faulty_test_runs']} faulty runs)")
    print(f"  • Median Detection Delay:          {audit['median_detection_delay_samples']} samples ({audit['median_detection_delay_minutes']} min after onset)")
    print(f"  • Normal-Run FPR (d00_te):         {audit.get('normal_run_fpr_pct', 0.0)}% (target < 5.0%)")
    print(f"  • Normal Run False Alarms:         {audit['normal_run_false_alarms']} (alert threshold >= 0.70)")
    print(f"  • Pre-onset False Alarms (t<160):  {audit['pre_onset_false_alarms']} / 21 runs")

    # 4. Save clean CPU-portable production artifacts
    os.makedirs(args.output_dir, exist_ok=True)
    bundle_path = os.path.join(args.output_dir, "bundle.joblib")
    lstm_path = os.path.join(args.output_dir, "lstm_fcn.pt")
    ae_path = os.path.join(args.output_dir, "autoencoder.pt")
    metrics_path = os.path.join(args.output_dir, "metrics.json")
    replay_parquet_path = os.path.join(args.output_dir, "replay_sample.parquet")
    zip_path = os.path.join(args.output_dir, "tep_artifacts.zip")

    print(f"\n[persistence] Serializing bundle to {bundle_path}...")
    joblib.dump(bundle, bundle_path, compress=3)

    print(f"[persistence] Saving PyTorch state dicts to {lstm_path} and {ae_path}...")
    torch.save(lstm_fcn.state_dict(), lstm_path)
    torch.save(autoencoder.state_dict(), ae_path)

    # Export compact held-out test replay subset (52 raw sensors + metadata only, ~2-3 MB)
    test_df = ds["test"].copy()
    if "fault_id" not in test_df.columns and "fault_class" in test_df.columns:
        test_df["fault_id"] = test_df["fault_class"].astype(np.int32)
    meta_cols = ["sample", "fault_class", "fault_id", "run_id", "fault_flag", "_onset"]
    slim_cols = [c for c in bundle["sensors"] if c in test_df.columns] + [c for c in meta_cols if c in test_df.columns]
    slim_df = test_df[slim_cols].copy()
    for col in bundle["sensors"]:
        if col in slim_df.columns:
            slim_df[col] = slim_df[col].astype(np.float32)

    # Clean up any legacy redundant gzip CSV if present
    csv_gz_path = os.path.join(args.output_dir, "replay_sample.csv.gz")
    if os.path.exists(csv_gz_path):
        try:
            os.remove(csv_gz_path)
            print(f"[persistence] Removed redundant legacy {csv_gz_path}")
        except Exception as e:
            print(f"[persistence] Note: Could not remove {csv_gz_path}: {e}")

    print(f"[persistence] Exporting slim held-out replay sample ({slim_df['run_id'].nunique()} runs, {len(slim_df)} rows, {len(slim_cols)} columns)...")
    try:
        slim_df.to_parquet(replay_parquet_path, index=False)
        print(f"  • Saved compact {replay_parquet_path} ({os.path.getsize(replay_parquet_path) / (1024*1024):.2f} MB)")
    except Exception as e:
        print(f"  • Parquet export failed ({e})")

    print(f"[persistence] Saving benchmark metrics to {metrics_path}...")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # Create downloadable zip
    print(f"[persistence] Packaging all artifacts into {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(bundle_path, arcname="bundle.joblib")
        z.write(lstm_path, arcname="lstm_fcn.pt")
        z.write(ae_path, arcname="autoencoder.pt")
        z.write(metrics_path, arcname="metrics.json")
        if os.path.exists(replay_parquet_path):
            z.write(replay_parquet_path, arcname="replay_sample.parquet")

    total_time = round(time.time() - t0, 1)
    print("\n" + "=" * 70)
    print(f"✅ TRAINING & EXPORT COMPLETED SUCCESSFULLY IN {total_time}s")
    print(f"📦 Production Artifacts: {args.output_dir}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
