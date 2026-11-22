import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Database,
  Download,
  FileSpreadsheet,
  FileText,
  HardDrive,
  RefreshCw,
  Search,
  Server,
  Trash2,
  Upload,
  Zap,
} from 'lucide-react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  analyzeCSV,
  getAuditLogs,
  getAuditLogsExportUrl,
  getSampleCSVUrl,
  getSystemInfo,
  reloadModels,
  resetDatabase,
  switchAdapter,
  controlStream,
} from '../api';
import { AuditLogItem, CSVAnalysisResult, SystemInfo } from '../types';

export const UtilitiesView: React.FC = React.memo(() => {
  // Sub-tab navigation
  const [subTab, setSubTab] = useState<'csv' | 'audit' | 'system'>('csv');

  // CSV Analyzer State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [csvResult, setCsvResult] = useState<CSVAnalysisResult | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [isLoadingAudit, setIsLoadingAudit] = useState(false);
  const [searchAction, setSearchAction] = useState('');
  const [searchUser, setSearchUser] = useState('');

  // System Info & Reload State
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [isLoadingSystem, setIsLoadingSystem] = useState(false);
  const [isReloading, setIsReloading] = useState(false);
  const [reloadMsg, setReloadMsg] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const handleResetDb = async () => {
    setIsResetting(true);
    setReloadMsg(null);
    try {
      const res = await resetDatabase();
      setReloadMsg(res.message);
      setShowResetConfirm(false);
      fetchSystemInfo();
      fetchLogs();
    } catch (e: any) {
      alert(`Database reset failed: ${e.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  // Load audit logs
  const fetchLogs = async () => {
    setIsLoadingAudit(true);
    try {
      const logs = await getAuditLogs(100, searchAction || undefined, searchUser || undefined);
      setAuditLogs(logs);
    } catch (e: any) {
      console.error(e);
    } finally {
      setIsLoadingAudit(false);
    }
  };

  // Load system info
  const fetchSystemInfo = async () => {
    setIsLoadingSystem(true);
    try {
      const info = await getSystemInfo();
      setSystemInfo(info);
    } catch (e: any) {
      console.error(e);
    } finally {
      setIsLoadingSystem(false);
    }
  };

  useEffect(() => {
    if (subTab === 'audit') {
      fetchLogs();
    } else if (subTab === 'system') {
      fetchSystemInfo();
    }
  }, [subTab]);

  // CSV file selection & execution
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setCsvError(null);
    }
  };

  const handleRunAnalysis = async () => {
    if (!selectedFile) return;
    setIsAnalyzing(true);
    setCsvError(null);
    try {
      const result = await analyzeCSV(selectedFile);
      setCsvResult(result);
    } catch (e: any) {
      setCsvError(e.message || 'Batch analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Model Hot-Reload
  const handleHotReload = async () => {
    setIsReloading(true);
    setReloadMsg(null);
    try {
      const res = await reloadModels();
      const originLabel = res.dataset_origin?.includes('real_tep') ? 'Real TEP Dataset' : 'Synthetic Baseline';
      const runsCount = res.available_runs_count ? ` (${res.available_runs_count} replay runs)` : '';
      setReloadMsg(
        res.status === 'success'
          ? `Models hot-reloaded successfully from disk! Origin: ${originLabel}${runsCount}.`
          : 'Model reload failed.'
      );
      fetchSystemInfo();
    } catch (e: any) {
      setReloadMsg(`Error reloading models: ${e.message}`);
    } finally {
      setIsReloading(false);
    }
  };

  // Adapter Switch
  const handleSwitchFeed = async (type: 'replay' | 'simulator') => {
    try {
      await switchAdapter(type);
      fetchSystemInfo();
    } catch (e: any) {
      alert(`Adapter switch failed: ${e.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Sub-tab Navigation Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 bg-[#0e172a] p-3 rounded-xl shadow-md">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setSubTab('csv')}
            className={`flex items-center space-x-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${
              subTab === 'csv'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <FileSpreadsheet className="h-4 w-4" />
            <span>CSV Batch Analyzer</span>
          </button>
          <button
            onClick={() => setSubTab('audit')}
            className={`flex items-center space-x-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${
              subTab === 'audit'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <FileText className="h-4 w-4" />
            <span>Compliance Audit Trail</span>
          </button>
          <button
            onClick={() => setSubTab('system')}
            className={`flex items-center space-x-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${
              subTab === 'system'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Server className="h-4 w-4" />
            <span>System Health & Ops</span>
          </button>
        </div>

        <div className="text-[11px] text-slate-400">
          Advisory Maintenance Operations • Zero Actuation Mode
        </div>
      </div>

      {/* ==================================================================== */}
      {/* SUB-TAB 1: CSV BATCH TELEMETRY ANALYZER                              */}
      {/* ==================================================================== */}
      {subTab === 'csv' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-[#090e1a] p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-blue-400" />
              <span>Offline TEP Batch Telemetry Analyzer</span>
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              Upload custom TEP run CSVs (raw 52 variables or named sensors) to run zero-leakage causal feature extraction, calibrated risk scoring, and 21-class fault diagnosis.
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-4">
              <label className="flex cursor-pointer items-center space-x-2 rounded-lg border border-slate-700 bg-slate-800/80 px-4 py-2.5 text-xs font-medium text-slate-200 hover:border-slate-600 hover:bg-slate-700 transition">
                <Upload className="h-4 w-4 text-blue-400" />
                <span>{selectedFile ? selectedFile.name : 'Choose CSV File...'}</span>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>

              <button
                onClick={handleRunAnalysis}
                disabled={!selectedFile || isAnalyzing}
                className="flex items-center space-x-2 rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg hover:bg-blue-500 disabled:opacity-50 transition"
              >
                {isAnalyzing ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Scoring Telemetry...</span>
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4" />
                    <span>Run Batch Inference</span>
                  </>
                )}
              </button>

              <a
                href={getSampleCSVUrl()}
                download="tep_sample_batch.csv"
                className="flex items-center space-x-1.5 rounded-lg border border-slate-700 bg-slate-900/90 px-3 py-2.5 text-xs font-medium text-slate-300 hover:text-white hover:border-slate-600 transition"
              >
                <Download className="h-3.5 w-3.5 text-emerald-400" />
                <span>Download Sample CSV (60 Steps)</span>
              </a>
            </div>

            {csvError && (
              <div className="mt-4 flex items-center space-x-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
                <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                <span>{csvError}</span>
              </div>
            )}
          </div>

          {/* Analysis Results Display */}
          {csvResult && (
            <div className="space-y-6">
              {/* Summary KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                  <div className="text-xs text-slate-400">Total Samples</div>
                  <div className="text-xl font-bold font-mono text-white mt-1">
                    {csvResult.total_rows}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">Time steps analyzed</div>
                </div>

                <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                  <div className="text-xs text-slate-400">Peak Risk Score</div>
                  <div
                    className={`text-xl font-bold font-mono mt-1 ${
                      csvResult.peak_risk >= 0.85
                        ? 'text-rose-400'
                        : csvResult.peak_risk >= 0.70
                        ? 'text-amber-400'
                        : 'text-emerald-400'
                    }`}
                  >
                    {csvResult.peak_risk.toFixed(4)}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Regime: {csvResult.overall_regime}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                  <div className="text-xs text-slate-400">Diagnosed Fault</div>
                  <div className="text-sm font-bold text-amber-300 mt-1 truncate">
                    Fault {csvResult.top_diagnosed_fault_id}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5 truncate">
                    {csvResult.top_diagnosed_fault_name}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                  <div className="text-xs text-slate-400">Primary Unit</div>
                  <div className="text-sm font-bold text-sky-300 mt-1 truncate">
                    {csvResult.primary_contributing_unit}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Excursions: {csvResult.alarms_triggered}
                  </div>
                </div>
              </div>

              {/* Risk Progression Timeline */}
              <div className="rounded-xl border border-slate-800 bg-[#090e1a] p-4 shadow-xl">
                <h4 className="text-sm font-bold text-slate-200 mb-3">
                  Batch Risk Progression & Hysteresis Envelope
                </h4>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={csvResult.time_series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="sample" stroke="#64748b" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 1]} stroke="#64748b" tick={{ fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0b1324',
                          borderColor: '#334155',
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <ReferenceLine y={0.70} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: 'WARNING (0.70)', fill: '#f59e0b', fontSize: 10 }} />
                      <ReferenceLine y={0.85} stroke="#ef4444" strokeDasharray="3 3" label={{ value: 'CRITICAL (0.85)', fill: '#ef4444', fontSize: 10 }} />
                      <Area type="monotone" dataKey="risk_score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} name="Risk Score" isAnimationActive={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Formatted Summary Card */}
              <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4 text-xs text-slate-300 whitespace-pre-line leading-relaxed font-mono">
                {csvResult.summary_markdown}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* SUB-TAB 2: COMPLIANCE AUDIT TRAIL                                    */}
      {/* ==================================================================== */}
      {subTab === 'audit' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-[#090e1a] p-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Filter by action..."
                  value={searchAction}
                  onChange={(e) => setSearchAction(e.target.value)}
                  className="rounded-lg border border-slate-700 bg-slate-800/90 pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-blue-500"
                />
              </div>

              <input
                type="text"
                placeholder="Filter by user..."
                value={searchUser}
                onChange={(e) => setSearchUser(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-blue-500"
              />

              <button
                onClick={fetchLogs}
                className="flex items-center space-x-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoadingAudit ? 'animate-spin' : ''}`} />
                <span>Search</span>
              </button>
            </div>

            <a
              href={getAuditLogsExportUrl()}
              download="tep_compliance_audit_trail.csv"
              className="flex items-center space-x-1.5 rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:text-white hover:border-slate-600 transition"
            >
              <Download className="h-3.5 w-3.5 text-blue-400" />
              <span>Export Audit Trail (CSV)</span>
            </a>
          </div>

          {/* Audit Logs Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-[#090e1a]">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 bg-[#0e172a] text-slate-400">
                <tr>
                  <th className="p-3">ID</th>
                  <th className="p-3">Timestamp (UTC)</th>
                  <th className="p-3">Action</th>
                  <th className="p-3">Operator</th>
                  <th className="p-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-4 text-center text-slate-500">
                      No audit records found.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40">
                      <td className="p-3 text-slate-400">#{log.id}</td>
                      <td className="p-3 text-slate-300">
                        {new Date(log.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>
                      <td className="p-3">
                        <span className="rounded bg-blue-950/80 px-2 py-0.5 text-[11px] font-semibold text-blue-300 border border-blue-800/50">
                          {log.action}
                        </span>
                      </td>
                      <td className="p-3 text-slate-200">{log.user}</td>
                      <td className="p-3 text-[11px] text-slate-400 max-w-xs truncate">
                        {JSON.stringify(log.details)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* SUB-TAB 3: SYSTEM HEALTH, OPS & MODEL HOT-RELOAD                    */}
      {/* ==================================================================== */}
      {subTab === 'system' && (
        <div className="space-y-6">
          {/* Controls Bar: Hot-reload & Feed Toggle */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 bg-[#090e1a] p-4">
            <div className="flex items-center space-x-3">
              <button
                onClick={handleHotReload}
                disabled={isReloading}
                className="flex items-center space-x-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50 transition"
              >
                <RefreshCw className={`h-4 w-4 ${isReloading ? 'animate-spin' : ''}`} />
                <span>Hot-Reload Models from Disk</span>
              </button>

              <button
                onClick={fetchSystemInfo}
                className="flex items-center space-x-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2 text-xs font-medium text-slate-300 hover:text-white"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Refresh Info</span>
              </button>

              <button
                onClick={() => setShowResetConfirm(true)}
                className="flex items-center space-x-1.5 rounded-lg border border-rose-800/60 bg-rose-950/40 px-3 py-2 text-xs font-medium text-rose-300 hover:bg-rose-900/60 transition"
              >
                <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                <span>Clear Alarms & Reset Demo DB</span>
              </button>
            </div>

            <div className="flex items-center space-x-2 text-xs">
              <span className="text-slate-400">Active Feed:</span>
              <button
                onClick={() => handleSwitchFeed('replay')}
                className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-200 hover:border-slate-500"
              >
                Switch to Replay
              </button>
              <button
                onClick={() => handleSwitchFeed('simulator')}
                className="rounded border border-amber-600/40 bg-amber-600/20 px-2.5 py-1 text-amber-300 hover:bg-amber-600/30"
              >
                Switch to Live Sim
              </button>
            </div>
          </div>

          {reloadMsg && (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300">
              {reloadMsg}
            </div>
          )}

          {/* Model Artifacts Cards */}
          {systemInfo && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-2">
                  <span>Model Bundle (XGBoost)</span>
                  <HardDrive className="h-4 w-4 text-emerald-400" />
                </div>
                <div className="space-y-1 font-mono text-xs text-slate-400">
                  <div>Status: <span className="text-emerald-400 font-bold">Loaded</span></div>
                  <div>Size: {systemInfo.model_artifacts.bundle.size_kb} KB</div>
                  <div className="truncate">Updated: {systemInfo.model_artifacts.bundle.modified || 'N/A'}</div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-2">
                  <span>Pillar 2: LSTM-FCN</span>
                  <HardDrive className="h-4 w-4 text-purple-400" />
                </div>
                <div className="space-y-1 font-mono text-xs text-slate-400">
                  <div>Status: <span className="text-purple-400 font-bold">Loaded (CPU)</span></div>
                  <div>Size: {systemInfo.model_artifacts.lstm_fcn.size_kb} KB</div>
                  <div className="truncate">Updated: {systemInfo.model_artifacts.lstm_fcn.modified || 'N/A'}</div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-2">
                  <span>Pillar 3: Autoencoder</span>
                  <HardDrive className="h-4 w-4 text-amber-400" />
                </div>
                <div className="space-y-1 font-mono text-xs text-slate-400">
                  <div>Status: <span className="text-amber-400 font-bold">Loaded (CPU)</span></div>
                  <div>Size: {systemInfo.model_artifacts.autoencoder.size_kb} KB</div>
                  <div className="truncate">Updated: {systemInfo.model_artifacts.autoencoder.modified || 'N/A'}</div>
                </div>
              </div>
            </div>
          )}

          {/* Database and Runtime Specs */}
          {systemInfo && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                <div className="flex items-center space-x-2 text-xs font-semibold text-slate-200 mb-3">
                  <Database className="h-4 w-4 text-blue-400" />
                  <span>Historian & Audit Persistence</span>
                </div>
                <div className="space-y-2 font-mono text-xs text-slate-300">
                  <div className="flex justify-between border-b border-slate-800/80 pb-1">
                    <span className="text-slate-400">Database Engine:</span>
                    <span className="font-bold text-white">{systemInfo.database.engine}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800/80 pb-1">
                    <span className="text-slate-400">Persistent Alarms:</span>
                    <span>{systemInfo.database.total_alarms} records</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Audit Logs:</span>
                    <span>{systemInfo.database.total_audit_logs} records</span>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0e172a] p-4">
                <div className="flex items-center space-x-2 text-xs font-semibold text-slate-200 mb-3">
                  <Activity className="h-4 w-4 text-emerald-400" />
                  <span>Runtime Environment</span>
                </div>
                <div className="space-y-2 font-mono text-xs text-slate-300">
                  <div className="flex justify-between border-b border-slate-800/80 pb-1 items-center">
                    <span className="text-slate-400">Dataset Origin:</span>
                    {systemInfo.runtime.dataset_origin?.includes('real_tep') ? (
                      <span className="inline-flex items-center gap-1 rounded bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 text-[11px] font-bold text-emerald-300">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        Real TEP Dataset ({systemInfo.runtime.dataset_origin === 'real_tep_kaggle_dat' ? 'Kaggle' : 'CSV'})
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded bg-amber-950/80 border border-amber-500/40 px-2 py-0.5 text-[11px] font-bold text-amber-300">
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                        Synthetic Baseline
                      </span>
                    )}
                  </div>
                  <div className="flex justify-between border-b border-slate-800/80 pb-1">
                    <span className="text-slate-400">Python / PyTorch:</span>
                    <span>{systemInfo.runtime.python_version} / {systemInfo.runtime.torch_version}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800/80 pb-1">
                    <span className="text-slate-400">Telemetry Adapter:</span>
                    <span className="text-sky-300 font-bold">{systemInfo.runtime.active_adapter}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">WebSocket Clients:</span>
                    <span>{systemInfo.runtime.active_ws_connections} connected</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          {/* Reset Demo DB Confirmation Modal */}
          {showResetConfirm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 animate-in fade-in">
              <div className="w-full max-w-md rounded-xl border border-rose-800/80 bg-[#0e172a] p-6 shadow-2xl">
                <div className="flex items-center space-x-3 text-rose-400">
                  <AlertTriangle className="h-6 w-6 flex-shrink-0" />
                  <h4 className="text-base font-bold text-white">Reset Demo Database?</h4>
                </div>
                <p className="mt-3 text-xs text-slate-300 leading-relaxed">
                  This will purge all historical alarms, past telemetry events, and audit logs from the historian, providing a fresh, pristine slate for live demonstrations. Model weights and pipeline configuration remain untouched.
                </p>
                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    onClick={() => setShowResetConfirm(false)}
                    disabled={isResetting}
                    className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleResetDb}
                    disabled={isResetting}
                    className="flex items-center space-x-1.5 rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500 shadow-lg"
                  >
                    {isResetting ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Resetting...</span>
                      </>
                    ) : (
                      <>
                        <Trash2 className="h-4 w-4" />
                        <span>Confirm Reset</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

