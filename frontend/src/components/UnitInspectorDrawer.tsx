import React from 'react';
import { AlertCircle, CheckCircle, ExternalLink, Sliders, X, Zap } from 'lucide-react';
import { PID_UNITS } from '../constants';
import { TelemetryFrame } from '../types';

interface UnitInspectorDrawerProps {
  unitName: string | null;
  currentFrame: TelemetryFrame | null;
  onClose: () => void;
  onOpenInExplorer: (unitName: string) => void;
}

export const UnitInspectorDrawer: React.FC<UnitInspectorDrawerProps> = React.memo(({
  unitName,
  currentFrame,
  onClose,
  onOpenInExplorer,
}) => {
  if (!unitName) return null;

  const unitInfo = PID_UNITS[unitName];
  if (!unitInfo) return null;

  const readings = currentFrame?.readings ?? {};
  const deviations = currentFrame?.deviations_sigma ?? {};
  const channelFlags = currentFrame?.channel_flags ?? {};
  const shapAttributions = currentFrame?.unit_attributions_pct ?? {};
  const shapPct = shapAttributions[unitName] ?? 0;

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-[#0b1324] text-slate-100 shadow-2xl border-l border-slate-800 animate-in slide-in-from-right duration-200">
      {/* Drawer Header */}
      <div className="flex items-start justify-between border-b border-slate-800 p-4">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-base font-bold text-white">{unitInfo.name}</h2>
            <span
              className={`rounded px-2 py-0.5 text-xs font-mono font-semibold ${
                shapPct >= 25
                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800/50'
                  : shapPct >= 15
                  ? 'bg-amber-950/80 text-amber-300 border border-amber-800/50'
                  : 'bg-blue-950/80 text-blue-300 border border-blue-800/50'
              }`}
            >
              TreeSHAP: {shapPct.toFixed(1)}%
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">{unitInfo.description}</p>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Drawer Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Measured Sensors */}
        <div>
          <div className="flex items-center space-x-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            <Zap className="h-3.5 w-3.5 text-amber-400" />
            <span>Measured Variables ({unitInfo.measuredSensors.length})</span>
          </div>
          <div className="divide-y divide-slate-800/60 rounded-lg border border-slate-800 bg-[#0e172a]">
            {unitInfo.measuredSensors.map((sensor) => {
              const val = readings[sensor];
              const dev = deviations[sensor];
              const flags = channelFlags[sensor] || [];
              const hasAnomaly = flags.some((f) => f !== 'HEALTHY' && f !== 'OK');
              const isHighDev = dev !== undefined && Math.abs(dev) >= 2.0;

              return (
                <div key={sensor} className="flex items-center justify-between p-2.5 text-xs">
                  <div className="flex-1 pr-2">
                    <div className="font-medium text-slate-200">{sensor}</div>
                    {hasAnomaly && (
                      <div className="mt-0.5 flex items-center gap-1 text-[10px] text-rose-400 font-mono">
                        <AlertCircle className="h-3 w-3" />
                        <span>{flags.filter((f) => f !== 'HEALTHY').join(', ')}</span>
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm font-semibold text-white">
                      {val !== undefined ? val.toFixed(2) : '—'}
                    </div>
                    {dev !== undefined && (
                      <span
                        className={`inline-block rounded px-1.5 py-0.2 text-[10px] font-mono ${
                          isHighDev
                            ? 'bg-rose-950/80 text-rose-300 font-bold'
                            : 'text-slate-400'
                        }`}
                      >
                        {dev > 0 ? `+${dev.toFixed(2)}` : dev.toFixed(2)}σ
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Manipulated Actuators / Valves */}
        {unitInfo.valves.length > 0 && (
          <div>
            <div className="flex items-center space-x-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              <Sliders className="h-3.5 w-3.5 text-sky-400" />
              <span>Manipulated Valves ({unitInfo.valves.length})</span>
            </div>
            <div className="divide-y divide-slate-800/60 rounded-lg border border-slate-800 bg-[#0e172a]">
              {unitInfo.valves.map((valve) => {
                const val = readings[valve];
                const dev = deviations[valve];
                return (
                  <div key={valve} className="flex items-center justify-between p-2.5 text-xs">
                    <div className="font-medium text-slate-200">{valve}</div>
                    <div className="text-right">
                      <span className="font-mono text-sm font-semibold text-sky-300">
                        {val !== undefined ? `${val.toFixed(1)}%` : '—'}
                      </span>
                      {dev !== undefined && (
                        <div className="text-[10px] text-slate-400 font-mono">
                          {dev > 0 ? `+${dev.toFixed(2)}` : dev.toFixed(2)}σ
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Drawer Footer Actions */}
      <div className="border-t border-slate-800 bg-[#0b1324] p-4">
        <button
          onClick={() => {
            onOpenInExplorer(unitName);
            onClose();
          }}
          className="flex w-full items-center justify-center space-x-2 rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-blue-500/20 hover:bg-blue-500 active:bg-blue-700 transition"
        >
          <ExternalLink className="h-4 w-4" />
          <span>Open in Telemetry Explorer</span>
        </button>
      </div>
    </div>
  );
});

