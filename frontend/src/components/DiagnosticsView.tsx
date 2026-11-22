import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BarChart2,
  HelpCircle,
  Info,
  Layers,
  ShieldAlert,
  Sliders,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getExplainability } from '../api';
import { TEP_FAULTS } from '../constants';
import { ExplainabilityResponse, TelemetryFrame } from '../types';

interface DiagnosticsViewProps {
  currentFrame: TelemetryFrame | null;
}

export const DiagnosticsView: React.FC<DiagnosticsViewProps> = React.memo(({ currentFrame }) => {
  const [explainData, setExplainData] = useState<ExplainabilityResponse | null>(null);
  const [isLoadingExplain, setIsLoadingExplain] = useState(false);

  const runId = currentFrame?.run_id ?? 'LIVE_STREAM';
  const currentStep = currentFrame?.step ?? 0;
  const top3 = currentFrame?.top_3_faults ?? [];
  const prescriptive = currentFrame?.prescriptive_actions;

  // Fetch explainability strictly when (runId, currentStep) primitive keys change
  useEffect(() => {
    let cancelled = false;
    async function loadExplain() {
      if (!currentFrame) return;
      setIsLoadingExplain(true);
      try {
        const data = await getExplainability(runId, currentStep);
        if (!cancelled) setExplainData(data);
      } catch (e) {
        console.warn('Explainability fetch deferred:', e);
      } finally {
        if (!cancelled) setIsLoadingExplain(false);
      }
    }

    loadExplain();
    return () => {
      cancelled = true;
    };
  }, [runId, currentStep]);

  // Format SHAP drivers for horizontal waterfall / contribution bar chart with useMemo
  const shapDrivers = useMemo(() => {
    return (explainData?.top_drivers ?? []).map((d) => ({
      feature: d.display_name || d.feature,
      value: parseFloat(d.shap_value.toFixed(4)),
      direction: d.direction,
    }));
  }, [explainData]);

  return (
    <div className="space-y-4">
      {/* Top Grid: Top-3 21-Class Fault Diagnosis & Advisory Prescriptive Actions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Panel A: 21-Class Top-3 Fault Isolation */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-5 shadow-xl">
          <div className="mb-3 flex items-center justify-between border-b border-slate-800 pb-2">
            <div>
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <BarChart2 className="h-4 w-4 text-blue-400" />
                <span>21-Class Fault Isolation (Top-3 Diagnosis)</span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Pillar 1 Softmax Classifier mapping 52-variable disturbance physics into exact Downs & Vogel root cause.
              </p>
            </div>
            <span className="rounded bg-blue-950 px-2 py-0.5 text-xs font-mono font-bold text-blue-300">
              Rank 1: Fault #{currentFrame?.top_fault_id ?? 0}
            </span>
          </div>

          <div className="space-y-3">
            {top3.map((f, idx) => {
              const fullName = TEP_FAULTS[f.fault_id] ?? f.name;
              const pct = (f.confidence * 100).toFixed(1);
              return (
                <div
                  key={f.fault_id}
                  className={`rounded-lg border p-3 transition ${
                    idx === 0
                      ? 'border-blue-500/40 bg-blue-950/20 shadow-md'
                      : 'border-slate-800 bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                          idx === 0
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        #{idx + 1}
                      </span>
                      <span className="font-semibold text-slate-200">
                        Fault {f.fault_id}: {fullName}
                      </span>
                    </div>
                    <span className="font-mono font-bold text-slate-100">{pct}%</span>
                  </div>

                  {/* Progress bar */}
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full transition-all duration-500 ${
                        idx === 0
                          ? 'bg-blue-500'
                          : idx === 1
                          ? 'bg-slate-500'
                          : 'bg-slate-600'
                      }`}
                      style={{ width: `${Math.max(0, Math.min(100, f.confidence * 100))}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Panel B: Human-in-the-Loop Prescriptive Action Card */}
        <div className="rounded-xl border border-amber-500/30 bg-[#0c1427] p-5 shadow-xl">
          <div className="mb-3 flex items-center justify-between border-b border-slate-800 pb-2">
            <div>
              <div className="flex items-center space-x-2">
                <ShieldAlert className="h-4 w-4 text-amber-400" />
                <h3 className="text-sm font-bold text-amber-300">
                  Prescriptive Action Recommendation
                </h3>
              </div>
              <p className="text-[11px] text-slate-400">
                Rule-based guidance synthesized from TreeSHAP drivers and physical unit boundaries.
              </p>
            </div>
            <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
              ADVISORY ONLY
            </span>
          </div>

          <div className="space-y-3 text-xs">
            {/* Title & Unit */}
            <div className="flex items-center justify-between rounded-lg bg-slate-900/90 p-2.5">
              <div>
                <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
                  Action Title
                </span>
                <span className="font-bold text-slate-100">
                  {prescriptive?.action_title ?? prescriptive?.diagnosed_fault ?? 'Nominal Plant Operating State'}
                </span>
              </div>
              <div className="text-right">
                <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
                  Primary Target Unit
                </span>
                <span className="font-bold text-sky-400">
                  {prescriptive?.primary_unit ?? 'None'}
                </span>
              </div>
            </div>

            {/* Setpoint Recommendations */}
            {prescriptive?.recommended_setpoints && Object.keys(prescriptive.recommended_setpoints).length > 0 && (
              <div>
                <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5 mb-1.5">
                  <Sliders className="h-3.5 w-3.5 text-blue-400" />
                  Target Valve Adjustments:
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(prescriptive.recommended_setpoints).map(([tag, adj]) => (
                    <div
                      key={tag}
                      className="rounded border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs"
                    >
                      <span className="text-slate-400">{tag}: </span>
                      <span className="font-bold text-amber-400">{adj}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action Steps */}
            <div>
              <span className="text-[11px] font-semibold text-slate-300 block mb-1">
                Standard Operational Checklist:
              </span>
              <ul className="space-y-1 text-slate-300 list-disc list-inside">
                {(prescriptive?.action_steps ?? [
                  'Maintain steady-state setpoints across all DCS loops.',
                  'Verify signal quality flags across 52 telemetry channels.',
                ]).map((step, i) => (
                  <li key={i} className="text-[11px]">
                    {step}
                  </li>
                ))}
              </ul>
            </div>

            {/* Disclaimer */}
            <div className="rounded border border-slate-800 bg-slate-950 p-2 text-[10px] text-slate-500">
              ⚠️ <strong>Strict Advisory Protocol:</strong> No automatic DCS actuator manipulation is permitted. Setpoints must be verified and adjusted manually by licensed chemical plant operators.
            </div>
          </div>
        </div>
      </div>

      {/* Middle Section: Real-Time TreeSHAP Waterfall Chart */}
      <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-5 shadow-xl">
        <div className="mb-3 flex items-center justify-between border-b border-slate-800 pb-2">
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              <span>Real-Time TreeSHAP Feature Attributions</span>
            </h3>
            <p className="text-[11px] text-slate-400">
              Exact Shapley values computed via TreeExplainer from XGBoost binary detector at sample t={currentStep}.
            </p>
          </div>
          <div className="flex items-center space-x-3 text-xs">
            <span className="flex items-center gap-1 text-rose-400 font-mono">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              +Δ Promotes Fault
            </span>
            <span className="flex items-center gap-1 text-blue-400 font-mono">
              <span className="h-2 w-2 rounded-full bg-blue-500" />
              -Δ Promotes Normal
            </span>
          </div>
        </div>

        {/* Bar Chart */}
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={shapDrivers}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 160, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" stroke="#64748b" tick={{ fontSize: 10 }} />
              <YAxis
                type="category"
                dataKey="feature"
                stroke="#cbd5e1"
                tick={{ fontSize: 10 }}
                width={150}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '8px',
                  fontSize: '11px',
                }}
              />
              <ReferenceLine x={0} stroke="#64748b" />
              <Bar dataKey="value" name="SHAP Contribution (log-odds)" isAnimationActive={false}>
                {shapDrivers.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.value >= 0 ? '#ef4444' : '#3b82f6'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
});


