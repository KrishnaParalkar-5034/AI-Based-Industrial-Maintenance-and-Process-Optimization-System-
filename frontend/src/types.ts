/**
 * TypeScript Interfaces strictly matching Backend FastAPI & WebSocket contracts.
 */

export interface TelemetryFrame {
  run_id: string;
  step: number;
  total_steps: number;
  timestamp: string;
  model_mode: 'stacked_ensemble' | 'xgboost' | 'lstm_fcn' | 'anomaly';
  readings: Record<string, number>;
  deviations_sigma: Record<string, number>;
  normal_baselines?: Record<string, { mean: number; std: number }>;
  channel_flags: Record<string, string[]>;
  sensor_health_score: number;
  risk_score: number;
  health_index: number;
  regime: 'NORMAL' | 'WARNING' | 'CRITICAL';
  alarm_flood: boolean;
  alarms_in_10min: number;
  unit_attributions_pct: Record<string, number>;
  top_fault_id: number;
  top_fault_name: string;
  top_fault_conf: number;
  top_3_faults: Array<{
    fault_id: number;
    name: string;
    confidence: number;
  }>;
  ttc: {
    ttc_active: boolean;
    ttc_minutes: number | null;
    ttc_samples: number | null;
    slope_per_min: number;
    r2: number;
    warn_threshold: number;
    crit_threshold: number;
  };
  pillar_scores: {
    xgb: number;
    lstm_fcn: number;
    anomaly: number;
    ensemble: number;
  };
  fault_onset_sample: number | null;
  inference_latency_ms: number;
  adapter_type?: 'replay' | 'simulator';
  active_fault?: number;
  prescriptive_actions: {
    urgency: string;
    diagnosed_fault: string;
    primary_unit: string;
    action_steps: string[];
    action_title?: string;
    target_valves?: string[];
    recommended_setpoints?: Record<string, string>;
  };
}

export interface StreamStatusResponse {
  is_playing: boolean;
  speed: number;
  current_run_id: string;
  current_step: number;
  total_steps: number;
  active_model_mode: string;
  available_runs: string[];
  hysteresis_thresholds: {
    warn_enter: number;
    warn_clear: number;
    crit_enter: number;
    crit_clear: number;
  };
  adapter_type?: 'replay' | 'simulator';
  active_fault_id?: number;
}

export interface StreamControlRequest {
  action: 'play' | 'pause' | 'seek' | 'speed' | 'switch_run' | 'toggle_mode' | 'inject_fault' | 'update_hysteresis' | 'switch_adapter';
  speed?: number;
  step?: number;
  run_id?: string;
  model_mode?: string;
  adapter_type?: 'replay' | 'simulator';
  fault_id?: number;
  warn_enter?: number;
  warn_clear?: number;
  crit_enter?: number;
  crit_clear?: number;
  operator_user?: string;
}

export interface AlarmResponse {
  id: number;
  timestamp: string;
  run_id: string;
  step: number;
  severity: 'WARNING' | 'CRITICAL';
  fault_diagnosis: string;
  top_unit: string;
  top_shap_drivers: Array<{
    feature: string;
    display_name?: string;
    shap_value: number;
    direction: string;
  }> | null;
  status: 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED' | 'FALSE_ALARM';
  acknowledged_by: string | null;
  operator_note: string | null;
  updated_at: string;
}

export interface AlarmUpdateRequest {
  status: 'ACKNOWLEDGED' | 'RESOLVED' | 'FALSE_ALARM';
  acknowledged_by?: string;
  operator_note?: string;
}

export interface ExplainabilityResponse {
  run_id: string;
  step: number;
  base_value: number;
  top_drivers: Array<{
    feature: string;
    display_name?: string;
    shap_value: number;
    direction: string;
  }>;
  unit_attributions_raw: Record<string, number>;
  unit_attributions_pct: Record<string, number>;
  primary_contributing_unit: string;
  prescriptive_actions: {
    urgency: string;
    diagnosed_fault: string;
    primary_unit: string;
    action_steps: string[];
    action_title?: string;
    target_valves?: string[];
    recommended_setpoints?: Record<string, string>;
  };
}

export interface BenchmarkMetrics {
  'Pillar 1: XGBoost (Binary)': {
    precision: number;
    recall: number;
    f1: number;
    tp: number;
    fp: number;
    fn: number;
    tn: number;
    roc_auc: number;
  };
  'Pillar 1: XGBoost (21-Class Multiclass)': {
    macro_f1: number;
    weighted_f1: number;
    per_fault_f1: Record<string, number>;
  };
  'Pillar 2: LSTM-FCN (Temporal Sequence)': {
    precision: number;
    recall: number;
    f1: number;
    roc_auc: number;
  };
  'Pillar 3: Autoencoder (Novelty MSE)': {
    precision: number;
    recall: number;
    f1: number;
    roc_auc: number;
  };
  'Stacked Heterogeneous Ensemble': {
    precision: number;
    recall: number;
    f1: number;
    roc_auc: number;
  };
  'Early Warning Audit (Detection Delay)': {
    total_test_runs: number;
    faulty_test_runs: number;
    detected_faults: number;
    missed_faults: number;
    detection_rate_pct: number;
    detectable_faults_total?: number;
    detectable_faults_detected?: number;
    detectable_detection_rate_pct?: number;
    median_detection_delay_samples: number;
    median_detection_delay_minutes: number;
    pre_onset_false_alarms: number;
    normal_run_false_alarms: number;
    normal_run_fpr_pct?: number;
    pre_onset_fpr_pct?: number;
  };
  dataset_origin?: string;
}

export interface ShiftHandoverReport {
  report_title: string;
  generated_at: string;
  advisory_notice: string;
  active_alarms_count: number;
  resolved_alarms_count: number;
  active_alarms: Array<{
    id: number;
    severity: string;
    unit: string;
    fault: string;
    status: string;
  }>;
  audit_logs: Array<{
    id: number;
    time: string;
    action: string;
    user: string;
  }>;
}

export interface CSVAnalysisResult {
  total_rows: number;
  peak_risk: number;
  mean_risk: number;
  overall_regime: 'NORMAL' | 'WARNING' | 'CRITICAL';
  alarms_triggered: number;
  top_diagnosed_fault_id: number;
  top_diagnosed_fault_name: string;
  top_fault_confidence: number;
  primary_contributing_unit: string;
  time_series: Array<{
    sample: number;
    risk_score: number;
    regime: string;
    top_fault_id: number;
    top_fault_name: string;
    confidence: number;
  }>;
  summary_markdown: string;
}

export interface AuditLogItem {
  id: number;
  timestamp: string;
  action: string;
  details: Record<string, any>;
  user: string;
}

export interface SystemInfo {
  model_artifacts: {
    bundle: { exists: boolean; size_kb: number; modified: string | null };
    lstm_fcn: { exists: boolean; size_kb: number; modified: string | null };
    autoencoder: { exists: boolean; size_kb: number; modified: string | null };
    metrics: { exists: boolean; modified: string | null };
  };
  database: {
    engine: string;
    total_alarms: number;
    total_audit_logs: number;
    status: string;
  };
  runtime: {
    python_version: string;
    torch_version: string;
    xgboost_version: string;
    active_adapter: string;
    active_run_id: string;
    active_model_mode: string;
    dataset_origin?: string;
    available_runs_count?: number;
    last_latency_ms: number;
    active_ws_connections: number;
  };
}
