import React, { useEffect, useState } from 'react';
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  Edit3,
  FileText,
  Filter,
  Printer,
  RefreshCw,
  Search,
  Settings2,
  ShieldAlert,
  User,
  X,
} from 'lucide-react';
import {
  controlStream,
  getAlarms,
  getShiftHandoverReportHtmlUrl,
  getShiftHandoverReportJson,
  updateAlarm,
} from '../api';
import {
  AlarmResponse,
  AlarmUpdateRequest,
  ShiftHandoverReport,
  StreamStatusResponse,
} from '../types';

interface AlarmConsoleViewProps {
  status: StreamStatusResponse | null;
  onRefreshStatus: () => void;
}

export const AlarmConsoleView: React.FC<AlarmConsoleViewProps> = React.memo(({
  status,
  onRefreshStatus,
}) => {
  const [alarms, setAlarms] = useState<AlarmResponse[]>([]);
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);

  // Operator Action Modal state
  const [selectedAlarm, setSelectedAlarm] = useState<AlarmResponse | null>(null);
  const [modalActionStatus, setModalActionStatus] = useState<'ACKNOWLEDGED' | 'RESOLVED' | 'FALSE_ALARM'>('ACKNOWLEDGED');
  const [operatorName, setOperatorName] = useState('Operator-1');
  const [operatorNote, setOperatorNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Shift Handover Modal state
  const [isHandoverModalOpen, setIsHandoverModalOpen] = useState(false);
  const [handoverData, setHandoverData] = useState<ShiftHandoverReport | null>(null);

  // Hysteresis Drawer state
  const [isHysteresisOpen, setIsHysteresisOpen] = useState(false);
  const [warnEnter, setWarnEnter] = useState(0.70);
  const [warnClear, setWarnClear] = useState(0.62);
  const [critEnter, setCritEnter] = useState(0.85);
  const [critClear, setCritClear] = useState(0.77);

  // Sync drawer values from server status strictly when primitive thresholds change
  const serverWarnEnter = status?.hysteresis_thresholds?.warn_enter;
  const serverWarnClear = status?.hysteresis_thresholds?.warn_clear;
  const serverCritEnter = status?.hysteresis_thresholds?.crit_enter;
  const serverCritClear = status?.hysteresis_thresholds?.crit_clear;

  useEffect(() => {
    if (serverWarnEnter !== undefined && serverWarnClear !== undefined && serverCritEnter !== undefined && serverCritClear !== undefined) {
      setWarnEnter(serverWarnEnter);
      setWarnClear(serverWarnClear);
      setCritEnter(serverCritEnter);
      setCritClear(serverCritClear);
    }
  }, [serverWarnEnter, serverWarnClear, serverCritEnter, serverCritClear]);

  // Load alarms
  const fetchAlarms = async () => {
    setIsLoading(true);
    try {
      const data = await getAlarms(selectedStatus || undefined, selectedSeverity || undefined, 100);
      setAlarms(data);
    } catch (e) {
      console.error('Failed to fetch alarms:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAlarms();
    const interval = setInterval(fetchAlarms, 4000);
    return () => clearInterval(interval);
  }, [selectedStatus, selectedSeverity]);

  // Handle Action submit
  const handleActionSubmit = async () => {
    if (!selectedAlarm) return;
    setIsSubmitting(true);
    try {
      const req: AlarmUpdateRequest = {
        status: modalActionStatus,
        acknowledged_by: operatorName,
        operator_note: operatorNote,
      };
      await updateAlarm(selectedAlarm.id, req);
      setSelectedAlarm(null);
      setOperatorNote('');
      await fetchAlarms();
    } catch (e: any) {
      alert(`Failed to update alarm: ${e.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Hysteresis Tuning submit
  const handleHysteresisSubmit = async () => {
    try {
      await controlStream({
        action: 'update_hysteresis',
        warn_enter: warnEnter,
        warn_clear: warnClear,
        crit_enter: critEnter,
        crit_clear: critClear,
      });
      setIsHysteresisOpen(false);
      onRefreshStatus();
      alert('ISA-18.2 deadband thresholds updated successfully.');
    } catch (e: any) {
      alert(`Failed to update hysteresis: ${e.message}`);
    }
  };

  // Open Shift Handover modal
  const handleOpenHandover = async () => {
    try {
      const data = await getShiftHandoverReportJson();
      setHandoverData(data);
      setIsHandoverModalOpen(true);
    } catch (e: any) {
      alert(`Failed to generate handover data: ${e.message}`);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Action Bar: Filters, Tuning Drawer, Shift Handover */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold text-slate-400 flex items-center gap-1">
            <Filter className="h-3.5 w-3.5" />
            Filter:
          </span>

          {/* Severity */}
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-200 outline-none"
          >
            <option value="">All Severities</option>
            <option value="CRITICAL">Critical Only</option>
            <option value="WARNING">Warning Only</option>
          </select>

          {/* Status */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-200 outline-none"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="RESOLVED">Resolved</option>
            <option value="FALSE_ALARM">False Alarm</option>
          </select>

          <button
            onClick={fetchAlarms}
            title="Refresh Alarm Console"
            className="rounded border border-slate-700 bg-slate-800 p-1 text-slate-300 hover:text-white"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Right buttons: Hysteresis Tuning & Shift Handover */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setIsHysteresisOpen(true)}
            className="flex items-center space-x-1.5 rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700"
          >
            <Settings2 className="h-3.5 w-3.5 text-blue-400" />
            <span>Tune Hysteresis</span>
          </button>

          <button
            onClick={handleOpenHandover}
            className="flex items-center space-x-1.5 rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 shadow"
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Shift Handover Report</span>
          </button>
        </div>
      </div>

      {/* Main Alarms Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-[#0c1427] shadow-xl">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-800 bg-slate-900/90 text-[11px] uppercase tracking-wider text-slate-400">
            <tr>
              <th className="py-2.5 px-3">Alarm ID</th>
              <th className="py-2.5 px-3">Severity</th>
              <th className="py-2.5 px-3">Timestamp / Step</th>
              <th className="py-2.5 px-3">Physical Unit</th>
              <th className="py-2.5 px-3">Diagnosed Root Cause</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Operator / Note</th>
              <th className="py-2.5 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {alarms.length > 0 ? (
              alarms.map((alarm) => {
                const isCrit = alarm.severity === 'CRITICAL';
                return (
                  <tr
                    key={alarm.id}
                    className="transition hover:bg-slate-800/40"
                  >
                    <td className="py-2.5 px-3 font-mono font-bold text-slate-300">
                      #{alarm.id}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold ${
                          isCrit
                            ? 'bg-rose-950 text-rose-300 border border-rose-500/40'
                            : 'bg-amber-950 text-amber-300 border border-amber-500/40'
                        }`}
                      >
                        {isCrit ? <AlertOctagon className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                        {alarm.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-400">
                      <div>{new Date(alarm.timestamp).toLocaleTimeString()}</div>
                      <div className="text-[10px] text-slate-500">Step t={alarm.step} ({alarm.run_id})</div>
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-sky-400">
                      {alarm.top_unit}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-200">
                      {alarm.fault_diagnosis}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold ${
                          alarm.status === 'ACTIVE'
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : alarm.status === 'ACKNOWLEDGED'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : alarm.status === 'RESOLVED'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : 'bg-slate-700 text-slate-300'
                        }`}
                      >
                        {alarm.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">
                      {alarm.acknowledged_by ? (
                        <div>
                          <span className="font-semibold text-slate-200 text-[11px]">
                            {alarm.acknowledged_by}
                          </span>
                          {alarm.operator_note && (
                            <p className="text-[10px] text-slate-400 italic">"{alarm.operator_note}"</p>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-500 text-[11px]">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => {
                          setSelectedAlarm(alarm);
                          setModalActionStatus(alarm.status === 'ACTIVE' ? 'ACKNOWLEDGED' : 'RESOLVED');
                          setOperatorNote(alarm.operator_note ?? '');
                        }}
                        className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] font-medium text-slate-200 hover:bg-slate-700"
                      >
                        Respond
                      </button>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={8} className="py-6 text-center text-slate-500">
                  No active or matching alarms recorded in database.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Operator Action / Note Modal */}
      {selectedAlarm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2 text-slate-100 font-bold">
                <Edit3 className="h-4 w-4 text-blue-400" />
                <span>Operator Response: Alarm #{selectedAlarm.id}</span>
              </div>
              <button
                onClick={() => setSelectedAlarm(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="py-4 space-y-3 text-xs">
              <div>
                <span className="text-slate-400 block mb-1">Target Action State:</span>
                <div className="grid grid-cols-3 gap-2">
                  {(['ACKNOWLEDGED', 'RESOLVED', 'FALSE_ALARM'] as const).map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setModalActionStatus(st)}
                      className={`rounded px-2.5 py-1.5 font-bold transition text-[11px] ${
                        modalActionStatus === st
                          ? 'bg-blue-600 text-white'
                          : 'border border-slate-800 bg-slate-800 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Console Operator Call-Sign:</label>
                <input
                  type="text"
                  value={operatorName}
                  onChange={(e) => setOperatorName(e.target.value)}
                  className="w-full rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Operational Assessment / RCA Note:</label>
                <textarea
                  rows={3}
                  value={operatorNote}
                  onChange={(e) => setOperatorNote(e.target.value)}
                  placeholder="E.g., Verified reactor cooling temp deviation. Setpoint adjusted +5% per advisory protocol."
                  className="w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 border-t border-slate-800 pt-3">
              <button
                onClick={() => setSelectedAlarm(null)}
                className="rounded px-3 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleActionSubmit}
                disabled={isSubmitting}
                className="rounded bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {isSubmitting ? 'Recording...' : 'Commit to Audit Trail'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hysteresis & Threshold Tuning Drawer Modal */}
      {isHysteresisOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2 text-slate-100 font-bold">
                <Settings2 className="h-4 w-4 text-blue-400" />
                <span>ISA-18.2 Alarm Deadband & Hysteresis Tuning</span>
              </div>
              <button
                onClick={() => setIsHysteresisOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="py-4 space-y-4 text-xs">
              <p className="text-slate-400">
                Configure dual-threshold deadband hysteresis to eliminate alarm chattering around supervisory limits.
              </p>

              {/* Warning Deadband */}
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 space-y-2">
                <span className="font-semibold text-amber-300 block">
                  WARNING Threshold Hysteresis
                </span>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 text-[11px] block">Enter Warning (&ge; P):</label>
                    <input
                      type="number"
                      step={0.01}
                      min={0.1}
                      max={0.9}
                      value={warnEnter}
                      onChange={(e) => setWarnEnter(parseFloat(e.target.value))}
                      className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-xs text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 text-[11px] block">Clear Warning (&lt; P):</label>
                    <input
                      type="number"
                      step={0.01}
                      min={0.1}
                      max={0.9}
                      value={warnClear}
                      onChange={(e) => setWarnClear(parseFloat(e.target.value))}
                      className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-xs text-slate-200"
                    />
                  </div>
                </div>
              </div>

              {/* Critical Deadband */}
              <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3 space-y-2">
                <span className="font-semibold text-rose-300 block">
                  CRITICAL Threshold Hysteresis
                </span>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 text-[11px] block">Enter Critical (&ge; P):</label>
                    <input
                      type="number"
                      step={0.01}
                      min={0.2}
                      max={1.0}
                      value={critEnter}
                      onChange={(e) => setCritEnter(parseFloat(e.target.value))}
                      className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-xs text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 text-[11px] block">Clear Critical (&lt; P):</label>
                    <input
                      type="number"
                      step={0.01}
                      min={0.2}
                      max={1.0}
                      value={critClear}
                      onChange={(e) => setCritClear(parseFloat(e.target.value))}
                      className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-xs text-slate-200"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-2 border-t border-slate-800 pt-3">
              <button
                onClick={() => setIsHysteresisOpen(false)}
                className="rounded px-3 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleHysteresisSubmit}
                className="rounded bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-500"
              >
                Apply Deadbands
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Shift Handover Report Modal */}
      {isHandoverModalOpen && handoverData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2 text-slate-100 font-bold">
                <FileText className="h-5 w-5 text-blue-400" />
                <span>Shift Handover & Plant Reliability Report</span>
              </div>
              <button
                onClick={() => setIsHandoverModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="py-4 space-y-4 overflow-y-auto text-xs flex-1 pr-1">
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800 flex justify-between items-center">
                <div>
                  <h4 className="font-bold text-slate-200">{handoverData.report_title}</h4>
                  <p className="text-[11px] text-slate-400">{handoverData.generated_at}</p>
                </div>
                <div className="text-right">
                  <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                    ADVISORY STANDARD
                  </span>
                </div>
              </div>

              {/* Active Alarms */}
              <div>
                <h5 className="font-semibold text-slate-300 mb-2">
                  Active Alarms Transferred to Next Shift ({handoverData.active_alarms_count}):
                </h5>
                <div className="rounded border border-slate-800 bg-slate-950/60 p-2 space-y-1">
                  {handoverData.active_alarms.length > 0 ? (
                    handoverData.active_alarms.map((a) => (
                      <div key={a.id} className="flex items-center justify-between py-1 border-b border-slate-800/40 text-[11px]">
                        <span className="font-mono text-slate-400">#{a.id}</span>
                        <span className="font-semibold text-rose-400">{a.severity}</span>
                        <span className="text-sky-300">{a.unit}</span>
                        <span className="text-slate-200">{a.fault}</span>
                        <span className="font-mono text-amber-400">{a.status}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500 italic py-1">No active unresolved alarms at shift handover.</p>
                  )}
                </div>
              </div>

              {/* Audit Logs */}
              <div>
                <h5 className="font-semibold text-slate-300 mb-2">
                  Recent Control Room Operator Actions:
                </h5>
                <div className="rounded border border-slate-800 bg-slate-950/60 p-2 space-y-1 font-mono text-[10px]">
                  {handoverData.audit_logs.map((log) => (
                    <div key={log.id} className="flex justify-between text-slate-400 py-0.5">
                      <span>[{log.time}]</span>
                      <span className="text-blue-300 font-semibold">{log.action}</span>
                      <span className="text-slate-300">{log.user}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-between items-center border-t border-slate-800 pt-4">
              <span className="text-[10px] text-slate-500">
                Official shift record stored in immutable SQLite audit journal.
              </span>
              <div className="flex space-x-2">
                <button
                  onClick={() => setIsHandoverModalOpen(false)}
                  className="rounded px-3 py-1.5 text-xs text-slate-400 hover:text-white"
                >
                  Close
                </button>
                <button
                  onClick={() => window.open(getShiftHandoverReportHtmlUrl(), '_blank')}
                  className="flex items-center space-x-1.5 rounded bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-500"
                >
                  <Printer className="h-3.5 w-3.5" />
                  <span>Print / Export PDF</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

