import {
  AlarmResponse,
  AlarmUpdateRequest,
  AuditLogItem,
  BenchmarkMetrics,
  CSVAnalysisResult,
  ExplainabilityResponse,
  ShiftHandoverReport,
  StreamControlRequest,
  StreamStatusResponse,
  SystemInfo,
} from './types';

const envBase = import.meta.env.VITE_API_BASE_URL;
const API_BASE = envBase !== undefined && envBase !== ''
  ? `${envBase.replace(/\/$/, '')}/api/v1`
  : (import.meta.env.PROD ? '/api/v1' : 'http://127.0.0.1:8000/api/v1');

export async function getStreamStatus(): Promise<StreamStatusResponse> {
  const res = await fetch(`${API_BASE}/stream/status`);
  if (!res.ok) throw new Error(`Failed to fetch stream status: ${res.statusText}`);
  return res.json();
}

export async function controlStream(req: StreamControlRequest): Promise<any> {
  const res = await fetch(`${API_BASE}/stream/control`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Stream control action failed: ${res.statusText}`);
  return res.json();
}

export async function getExplainability(runId: string, step: number): Promise<ExplainabilityResponse> {
  const res = await fetch(`${API_BASE}/explain/${encodeURIComponent(runId)}/${step}`);
  if (!res.ok) throw new Error(`Failed to fetch explainability: ${res.statusText}`);
  return res.json();
}

export async function getAlarms(status?: string, severity?: string, limit: number = 50): Promise<AlarmResponse[]> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (severity) params.append('severity', severity);
  params.append('limit', limit.toString());

  const res = await fetch(`${API_BASE}/alarms?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch alarms: ${res.statusText}`);
  return res.json();
}

export async function updateAlarm(alarmId: number, req: AlarmUpdateRequest): Promise<AlarmResponse> {
  const res = await fetch(`${API_BASE}/alarms/${alarmId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Failed to update alarm: ${res.statusText}`);
  return res.json();
}

export async function getModelBenchmarks(): Promise<BenchmarkMetrics> {
  const res = await fetch(`${API_BASE}/models/benchmarks`);
  if (!res.ok) throw new Error(`Failed to fetch model benchmarks: ${res.statusText}`);
  return res.json();
}

export async function getShiftHandoverReportJson(): Promise<ShiftHandoverReport> {
  const res = await fetch(`${API_BASE}/reports/shift-handover?format=json`);
  if (!res.ok) throw new Error(`Failed to fetch shift handover JSON: ${res.statusText}`);
  return res.json();
}

export function getShiftHandoverReportHtmlUrl(): string {
  return `${API_BASE}/reports/shift-handover?format=html`;
}

export async function analyzeCSV(file: File): Promise<CSVAnalysisResult> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/analyze/csv`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to analyze CSV');
  }
  return res.json();
}

export function getSampleCSVUrl(): string {
  return `${API_BASE}/analyze/sample-csv`;
}

export async function getAuditLogs(limit: number = 50, action?: string, user?: string): Promise<AuditLogItem[]> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  if (action) params.append('action', action);
  if (user) params.append('user', user);

  const res = await fetch(`${API_BASE}/audit-logs?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch audit logs: ${res.statusText}`);
  return res.json();
}

export function getAuditLogsExportUrl(): string {
  return `${API_BASE}/audit-logs/export`;
}

export async function getSystemInfo(): Promise<SystemInfo> {
  const res = await fetch(`${API_BASE}/system/info`);
  if (!res.ok) throw new Error(`Failed to fetch system info: ${res.statusText}`);
  return res.json();
}

export async function reloadModels(): Promise<{
  status: string;
  models_loaded: boolean;
  has_lstm?: boolean;
  has_autoencoder?: boolean;
  dataset_origin?: string;
  available_runs_count?: number;
  current_run_id?: string;
  timestamp: string;
}> {
  const res = await fetch(`${API_BASE}/models/reload`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to reload models: ${res.statusText}`);
  return res.json();
}

export async function switchAdapter(adapterType: 'replay' | 'simulator'): Promise<any> {
  return controlStream({
    action: 'switch_adapter',
    adapter_type: adapterType,
  });
}

export async function resetDatabase(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/system/reset-db`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to reset database: ${res.statusText}`);
  return res.json();
}
