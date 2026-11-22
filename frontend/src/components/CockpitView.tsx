import React, { useMemo, useState } from 'react';
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle,
  Clock,
  Layers,
  TrendingUp,
  Zap,
} from 'lucide-react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { TelemetryFrame } from '../types';
import { PidDigitalTwin } from './PidDigitalTwin';
import { UnitInspectorDrawer } from './UnitInspectorDrawer';

interface CockpitViewProps {
  currentFrame: TelemetryFrame | null;
  history: TelemetryFrame[];
  selectedUnit: string | null;
  onSelectUnit: (unitName: string | null) => void;
  onOpenInExplorer?: (unitName: string) => void;
}

export const CockpitView: React.FC<CockpitViewProps> = React.memo(({
  currentFrame,
  history,
  selectedUnit,
  onSelectUnit,
  onOpenInExplorer,
}) => {
  // Pillar overlay toggles
  const [showXgb, setShowXgb] = useState(true);
  const [showLstm, setShowLstm] = useState(true);
  const [showAnom, setShowAnom] = useState(false);
  const [showEnsemble, setShowEnsemble] = useState(true);

  const healthIndex = currentFrame?.health_index ?? 100.0;
  const riskScore = currentFrame?.risk_score ?? 0.0;
  const regime = currentFrame?.regime ?? 'NORMAL';
  const alarmFlood = currentFrame?.alarm_flood ?? false;
  const alarmsCount = currentFrame?.alarms_in_10min ?? 0;
  const ttc = currentFrame?.ttc;

  // Prepare chart series from history with useMemo
  const chartData = useMemo(() => {
    return history.map((f) => ({
      step: f.step,
      ensemble: f.pillar_scores?.ensemble ?? f.risk_score,
      xgb: f.pillar_scores?.xgb ?? 0,
      lstm: f.pillar_scores?.lstm_fcn ?? 0,
      anomaly: f.pillar_scores?.anomaly ?? 0,
    }));
  }, [history]);

  // Helper colors for ISA-18.2 regime
  const getRegimeBadge = () => {
    switch (regime) {
      case 'CRITICAL':
        return {
          bg: 'bg-red-500/20 text-red-400 border-red-500/40',
          icon: <AlertOctagon className="h-5 w-5 text-red-400 animate-bounce" />,
          label: 'CRITICAL REGIME',
        };
      case 'WARNING':
        return {
          bg: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
          icon: <AlertTriangle className="h-5 w-5 text-amber-400 animate-pulse" />,
          label: 'WARNING REGIME',
        };
      default:
        return {
          bg: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
          icon: <CheckCircle className="h-5 w-5 text-emerald-400" />,
          label: 'NORMAL OPERATION',
        };
    }
  };

  const regBadge = getRegimeBadge();

  return (
    <div className="space-y-4">
      {/* Top Metric Cards: Health Index, Risk Score, Regime, TTC, Flood Alert */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: Plant Health Index */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Plant Health Index</span>
            <Zap className="h-4 w-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`font-mono text-3xl font-extrabold ${
                healthIndex >= 85
                  ? 'text-emerald-400'
                  : healthIndex >= 60
                  ? 'text-amber-400'
                  : 'text-rose-400'
              }`}
            >
              {healthIndex.toFixed(1)}%
            </span>
            <span className="text-xs text-slate-500">Nominal Target: &gt;90%</span>
          </div>
          {/* Progress bar */}
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className={`h-full transition-all duration-500 ${
                healthIndex >= 85
                  ? 'bg-emerald-500'
                  : healthIndex >= 60
                  ? 'bg-amber-500'
                  : 'bg-rose-500'
              }`}
              style={{ width: `${Math.max(0, Math.min(100, healthIndex))}%` }}
            />
          </div>
        </div>

        {/* Card 2: Risk Score & ISA-18.2 Regime */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Unified Risk Probability</span>
            <span className="font-mono text-[11px] text-slate-400">
              P = {riskScore.toFixed(4)}
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div
              className={`flex items-center space-x-2 rounded-lg border px-3 py-1.5 ${regBadge.bg}`}
            >
              {regBadge.icon}
              <span className="text-sm font-bold tracking-wider">{regBadge.label}</span>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Deadbands:</span>
            <span>WARN 0.70/0.62 • CRIT 0.85/0.77</span>
          </div>
        </div>

        {/* Card 3: Estimated Time-to-Critical (TTC) */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Time-to-Critical (TTC)</span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2">
            {ttc?.ttc_active && ttc.ttc_minutes ? (
              <div>
                <span className="font-mono text-3xl font-extrabold text-amber-400">
                  {ttc.ttc_minutes.toFixed(1)}{' '}
                  <span className="text-base font-normal text-slate-300">min</span>
                </span>
                <p className="mt-1 text-[11px] text-rose-300 flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  Climbing at +{(ttc.slope_per_min * 100).toFixed(2)}% risk/min
                </p>
              </div>
            ) : (
              <div>
                <span className="font-mono text-2xl font-bold text-emerald-400">
                  STABLE
                </span>
                <p className="mt-1 text-[11px] text-slate-400">
                  No positive linear drift toward critical limit.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Card 4: Alarm Flood & 10-Minute Rate */}
        <div
          className={`rounded-xl border p-4 shadow-lg transition ${
            alarmFlood
              ? 'border-rose-500/50 bg-rose-950/20 shadow-[0_0_15px_rgba(244,63,94,0.15)]'
              : 'border-slate-800 bg-[#0c1427]'
          }`}
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>ISA-18.2 Alarm Flood Rate</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                alarmFlood
                  ? 'bg-rose-600 text-white animate-pulse'
                  : 'bg-slate-800 text-slate-300'
              }`}
            >
              {alarmFlood ? 'FLOOD ACTIVE' : 'NORMAL LOAD'}
            </span>
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`font-mono text-3xl font-extrabold ${
                alarmFlood ? 'text-rose-400' : 'text-slate-100'
              }`}
            >
              {alarmsCount}
            </span>
            <span className="text-xs text-slate-400">alarms in trailing 10 min</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            Threshold: &gt;10 alarms/10 min triggers supervisory flood suppression.
          </p>
        </div>
      </div>

      {/* Main Section: Interactive Vector SVG P&ID Digital Twin */}
      <PidDigitalTwin
        currentFrame={currentFrame}
        selectedUnit={selectedUnit}
        onSelectUnit={onSelectUnit}
      />

      {/* Bottom Section: Live Risk Timeline & Multi-Pillar Ensemble Overlay */}
      <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Layers className="h-4 w-4 text-blue-400" />
              <span>Multi-Pillar Risk Progression & ISA-18.2 Hysteresis Bands</span>
            </h3>
            <p className="text-[11px] text-slate-400">
              Real-time progression showing Pillar 1 (XGBoost), Pillar 2 (LSTM-FCN), Pillar 3 (Autoencoder), and the Unified Stacked Ensemble.
            </p>
          </div>

          {/* Pillar Overlay Checkboxes */}
          <div className="flex items-center space-x-3 text-xs">
            <label className="flex items-center space-x-1.5 cursor-pointer text-slate-300 hover:text-white">
              <input
                type="checkbox"
                checked={showEnsemble}
                onChange={(e) => setShowEnsemble(e.target.checked)}
                className="rounded accent-blue-500"
              />
              <span className="font-semibold text-blue-400">Stacked Ensemble</span>
            </label>

            <label className="flex items-center space-x-1.5 cursor-pointer text-slate-300 hover:text-white">
              <input
                type="checkbox"
                checked={showXgb}
                onChange={(e) => setShowXgb(e.target.checked)}
                className="rounded accent-emerald-500"
              />
              <span className="text-emerald-400">XGBoost</span>
            </label>

            <label className="flex items-center space-x-1.5 cursor-pointer text-slate-300 hover:text-white">
              <input
                type="checkbox"
                checked={showLstm}
                onChange={(e) => setShowLstm(e.target.checked)}
                className="rounded accent-purple-500"
              />
              <span className="text-purple-400">LSTM-FCN</span>
            </label>

            <label className="flex items-center space-x-1.5 cursor-pointer text-slate-300 hover:text-white">
              <input
                type="checkbox"
                checked={showAnom}
                onChange={(e) => setShowAnom(e.target.checked)}
                className="rounded accent-amber-500"
              />
              <span className="text-amber-400">Autoencoder MSE</span>
            </label>
          </div>
        </div>

        {/* Timeline Chart */}
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="step" stroke="#64748b" tick={{ fontSize: 10 }} />
              <YAxis domain={[0, 1.0]} stroke="#64748b" tick={{ fontSize: 10 }} ticks={[0, 0.25, 0.5, 0.7, 0.85, 1.0]} />

              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '8px',
                  fontSize: '11px',
                }}
              />

              {/* Shaded Hysteresis Zones */}
              {/* Critical Zone */}
              <ReferenceArea y1={0.85} y2={1.0} fill="#ef4444" fillOpacity={0.12} />
              {/* Warning Zone */}
              <ReferenceArea y1={0.70} y2={0.85} fill="#f59e0b" fillOpacity={0.08} />

              {/* Threshold Lines */}
              <ReferenceLine y={0.85} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'CRIT (0.85)', fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }} />
              <ReferenceLine y={0.77} stroke="#ef4444" strokeDasharray="2 2" strokeOpacity={0.6} />
              <ReferenceLine y={0.70} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: 'WARN (0.70)', fill: '#f59e0b', fontSize: 10, position: 'insideTopRight' }} />
              <ReferenceLine y={0.62} stroke="#f59e0b" strokeDasharray="2 2" strokeOpacity={0.6} />

              {/* Multi-Pillar Lines */}
              {showEnsemble && (
                <Area
                  type="monotone"
                  dataKey="ensemble"
                  stroke="#3b82f6"
                  strokeWidth={2.5}
                  fill="url(#ensembleGrad)"
                  name="Stacked Ensemble"
                  isAnimationActive={false}
                />
              )}

              {showXgb && (
                <Line
                  type="monotone"
                  dataKey="xgb"
                  stroke="#10b981"
                  strokeWidth={1.5}
                  dot={false}
                  name="Pillar 1: XGBoost"
                  isAnimationActive={false}
                />
              )}

              {showLstm && (
                <Line
                  type="monotone"
                  dataKey="lstm"
                  stroke="#a855f7"
                  strokeWidth={1.5}
                  dot={false}
                  name="Pillar 2: LSTM-FCN"
                  isAnimationActive={false}
                />
              )}

              {showAnom && (
                <Line
                  type="monotone"
                  dataKey="anomaly"
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Pillar 3: Autoencoder MSE"
                  isAnimationActive={false}
                />
              )}

              <defs>
                <linearGradient id="ensembleGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                </linearGradient>
              </defs>
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Slide-over Unit Inspector Drawer on P&ID click */}
      <UnitInspectorDrawer
        unitName={selectedUnit}
        currentFrame={currentFrame}
        onClose={() => onSelectUnit(null)}
        onOpenInExplorer={(u) => {
          if (onOpenInExplorer) onOpenInExplorer(u);
        }}
      />
    </div>
  );
});

