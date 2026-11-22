import React, { useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Filter,
  Search,
  ShieldCheck,
  Snowflake,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { PID_UNITS, SENSOR_DETAILS } from '../constants';
import { TelemetryFrame } from '../types';

interface TelemetryExplorerViewProps {
  currentFrame: TelemetryFrame | null;
  history: TelemetryFrame[];
  selectedUnit: string | null;
  onSelectUnit: (unitName: string | null) => void;
  selectedSensor?: string | null;
  onSelectSensor?: (sensorName: string) => void;
}

export const TelemetryExplorerView: React.FC<TelemetryExplorerViewProps> = React.memo(({
  currentFrame,
  history,
  selectedUnit,
  onSelectUnit,
  selectedSensor: propSelectedSensor,
  onSelectSensor: propOnSelectSensor,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [internalSensor, setInternalSensor] = useState<string>('Reactor Temperature');
  const selectedSensor = propSelectedSensor ?? internalSensor;
  const setSelectedSensor = (s: string) => {
    setInternalSensor(s);
    propOnSelectSensor?.(s);
  };

  const readings = currentFrame?.readings ?? {};
  const deviations = currentFrame?.deviations_sigma ?? {};
  const channelFlags = currentFrame?.channel_flags ?? {};
  const sensorHealth = currentFrame?.sensor_health_score ?? 100.0;

  // Filter sensors by selected unit and search term
  const filteredSensors = useMemo(() => {
    let list: string[] = [];
    if (selectedUnit && PID_UNITS[selectedUnit]) {
      list = [...PID_UNITS[selectedUnit].measuredSensors, ...PID_UNITS[selectedUnit].valves];
    } else {
      list = Object.keys(readings).length > 0 ? Object.keys(readings) : Object.keys(SENSOR_DETAILS);
    }

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      list = list.filter((s) => {
        const details = SENSOR_DETAILS[s];
        return s.toLowerCase().includes(q) || (details && details.tag.toLowerCase().includes(q));
      });
    }

    return list;
  }, [selectedUnit, searchTerm, readings]);

  // Aggregate channel flag stats
  const flaggedChannels = useMemo(() => {
    const frozen: string[] = [];
    const dropouts: string[] = [];
    const spikes: string[] = [];

    Object.entries(channelFlags).forEach(([sensor, flags]) => {
      if (flags.includes('FROZEN')) frozen.push(sensor);
      if (flags.includes('DROPOUT_NAN')) dropouts.push(sensor);
      if (flags.includes('OUTLIER_SPIKE')) spikes.push(sensor);
    });

    return { frozen, dropouts, spikes, total: Object.keys(channelFlags).length };
  }, [channelFlags]);

  // Prepare chart series for selected sensor across history
  const sensorChartData = useMemo(() => {
    return history.map((f) => ({
      step: f.step,
      value: f.readings?.[selectedSensor] ?? 0,
      sigma: f.deviations_sigma?.[selectedSensor] ?? 0,
    }));
  }, [history, selectedSensor]);

  // Selected sensor details
  const selDetails = SENSOR_DETAILS[selectedSensor] ?? { tag: 'xmeas', unit: '', min: 0, max: 100 };
  const currentVal = readings[selectedSensor] ?? 0;
  const currentSigma = deviations[selectedSensor] ?? 0;
  const currentFlags = channelFlags[selectedSensor] ?? [];
  const isHealthyFlag = (f: string) => f === 'HEALTHY' || f === 'OK';
  const abnormalFlags = currentFlags.filter((f) => !isHealthyFlag(f));

  // Baseline envelope calculations from ground truth bundle
  const baseline = currentFrame?.normal_baselines?.[selectedSensor];
  const mean = baseline?.mean ?? (readings[selectedSensor] !== undefined ? readings[selectedSensor] : 50.0);
  const std = baseline?.std ?? (Math.abs(mean * 0.03) || 1.0);
  const envMin = mean - 2.0 * std;
  const envMax = mean + 2.0 * std;

  // Auto-pad YAxis domain so ±2.0σ envelope is always completely visible inside [mean - 2.5*std, mean + 2.5*std] alongside data
  const yDomain = useMemo(() => {
    const vals = sensorChartData.map((d) => d.value).filter((v) => !isNaN(v));
    const dataMin = vals.length > 0 ? Math.min(...vals) : mean;
    const dataMax = vals.length > 0 ? Math.max(...vals) : mean;
    const padMin = Math.min(dataMin, mean - 2.5 * std);
    const padMax = Math.max(dataMax, mean + 2.5 * std);
    const span = Math.max(1.0, padMax - padMin);
    return [Math.floor(padMin - span * 0.05), Math.ceil(padMax + span * 0.05)];
  }, [sensorChartData, mean, std]);

  return (
    <div className="space-y-4">
      {/* Top Banner: Signal Quality Monitor & Badges */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        {/* Composite Sensor Health */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Signal Quality Score</span>
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`font-mono text-3xl font-extrabold ${
                sensorHealth >= 95
                  ? 'text-emerald-400'
                  : sensorHealth >= 80
                  ? 'text-amber-400'
                  : 'text-rose-400'
              }`}
            >
              {sensorHealth.toFixed(1)}%
            </span>
            <span className="text-xs text-slate-400">52 channels</span>
          </div>
        </div>

        {/* Frozen Sensors */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Frozen Channels (Zero Var)</span>
            <Snowflake className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`font-mono text-3xl font-extrabold ${
                flaggedChannels.frozen.length > 0 ? 'text-cyan-400' : 'text-slate-200'
              }`}
            >
              {flaggedChannels.frozen.length}
            </span>
            <span className="text-xs text-slate-500">N=10 flatline check</span>
          </div>
        </div>

        {/* Dropout / Missing */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Signal Dropouts / NaNs</span>
            <AlertCircle className="h-4 w-4 text-rose-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`font-mono text-3xl font-extrabold ${
                flaggedChannels.dropouts.length > 0 ? 'text-rose-400' : 'text-slate-200'
              }`}
            >
              {flaggedChannels.dropouts.length}
            </span>
            <span className="text-xs text-slate-500">Causal ffill recovery</span>
          </div>
        </div>

        {/* Extreme Spikes */}
        <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Outlier Spikes (|z| &gt; 8)</span>
            <TrendingUp className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`font-mono text-3xl font-extrabold ${
                flaggedChannels.spikes.length > 0 ? 'text-amber-400' : 'text-slate-200'
              }`}
            >
              {flaggedChannels.spikes.length}
            </span>
            <span className="text-xs text-slate-500">Electrical noise flag</span>
          </div>
        </div>
      </div>

      {/* Main Inspection Chart: Single Selected Sensor with ±2σ Normal Envelope */}
      <div className="rounded-xl border border-slate-800 bg-[#0c1427] p-4 shadow-xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="rounded bg-blue-950 px-2 py-0.5 font-mono text-xs font-bold text-blue-300">
                {selDetails.tag}
              </span>
              <h3 className="text-base font-bold text-slate-100">{selectedSensor}</h3>
              {abnormalFlags.map((fl) => (
                <span
                  key={fl}
                  className="rounded bg-rose-600/20 px-2 py-0.5 text-[10px] font-bold text-rose-300 border border-rose-500/30"
                >
                  {fl}
                </span>
              ))}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Current Reading:{' '}
              <span className="font-mono font-bold text-slate-200">
                {currentVal.toFixed(2)} {selDetails.unit}
              </span>{' '}
              • Deviation:{' '}
              <span
                className={`font-mono font-bold ${
                  Math.abs(currentSigma) > 3
                    ? 'text-rose-400'
                    : Math.abs(currentSigma) > 2
                    ? 'text-amber-400'
                    : 'text-emerald-400'
                }`}
              >
                {currentSigma > 0 ? `+${currentSigma.toFixed(2)}` : currentSigma.toFixed(2)}σ
              </span>
            </p>
          </div>

          <div className="text-xs text-slate-400 font-mono">
            Shaded Zone: ±2.0σ Nominal Operating Envelope [{envMin.toFixed(1)} — {envMax.toFixed(1)} {selDetails.unit}]
          </div>
        </div>

        {/* Time-Series Chart */}
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sensorChartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="step" stroke="#64748b" tick={{ fontSize: 10 }} />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 10 }}
                domain={yDomain}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '8px',
                  fontSize: '11px',
                }}
              />
              {/* Shaded ±2.0σ Normal Operating Envelope */}
              <ReferenceArea
                y1={envMin}
                y2={envMax}
                fill="#10b981"
                fillOpacity={0.12}
                stroke="#10b981"
                strokeOpacity={0.35}
                strokeDasharray="3 3"
                label={{
                  value: '±2.0σ Operating Envelope',
                  position: 'insideTopLeft',
                  fill: '#10b981',
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />
              <ReferenceLine
                y={mean}
                stroke="#10b981"
                strokeDasharray="2 2"
                strokeOpacity={0.5}
                label={{
                  value: `Mean (${mean.toFixed(1)})`,
                  position: 'insideRight',
                  fill: '#10b981',
                  fontSize: 9,
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#38bdf8"
                strokeWidth={2}
                dot={{ r: 2, fill: '#38bdf8' }}
                name={`${selectedSensor} (${selDetails.unit})`}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Filter Bar: Unit Pills & Search */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        {/* Unit Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => onSelectUnit(null)}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
              selectedUnit === null
                ? 'bg-blue-600 text-white shadow'
                : 'border border-slate-800 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            All 52 Sensors
          </button>
          {Object.keys(PID_UNITS).map((uName) => (
            <button
              key={uName}
              onClick={() => onSelectUnit(uName)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                selectedUnit === uName
                  ? 'bg-blue-600 text-white shadow'
                  : 'border border-slate-800 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {uName}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative min-w-[200px]">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search tag or name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-lg border border-slate-800 bg-slate-900/90 py-1.5 pl-8 pr-3 text-xs text-slate-200 outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* 52-Variable Sensor Grid & Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-[#0c1427] shadow-xl">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] uppercase tracking-wider text-slate-400">
            <tr>
              <th className="py-2.5 px-3">Tag</th>
              <th className="py-2.5 px-3">Physical Variable Name</th>
              <th className="py-2.5 px-3">Current Value</th>
              <th className="py-2.5 px-3">Engineering Unit</th>
              <th className="py-2.5 px-3">
                Deviation (<span className="normal-case">σ</span>)
              </th>
              <th className="py-2.5 px-3">Quality Health</th>
              <th className="py-2.5 px-3 text-right">Inspect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {filteredSensors.map((sensorName) => {
              const details = SENSOR_DETAILS[sensorName] ?? { tag: 'xmeas', unit: '' };
              const val = readings[sensorName] ?? 0;
              const sigma = deviations[sensorName] ?? 0;
              const flags = channelFlags[sensorName] ?? [];
              const abnormal = flags.filter((f) => !isHealthyFlag(f));
              const isSelected = selectedSensor === sensorName;

              return (
                <tr
                  key={sensorName}
                  onClick={() => setSelectedSensor(sensorName)}
                  className={`cursor-pointer transition hover:bg-slate-800/40 ${
                    isSelected ? 'bg-blue-950/30' : ''
                  }`}
                >
                  <td className="py-2 px-3 font-mono font-semibold text-blue-400">
                    {details.tag}
                  </td>
                  <td className="py-2 px-3 font-medium text-slate-200">
                    {sensorName}
                  </td>
                  <td className="py-2 px-3 font-mono font-bold text-slate-100">
                    {val.toFixed(2)}
                  </td>
                  <td className="py-2 px-3 text-slate-400">
                    {details.unit}
                  </td>
                  <td className="py-2 px-3 font-mono">
                    <span
                      className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        Math.abs(sigma) >= 3.0
                          ? 'bg-rose-950 text-rose-300'
                          : Math.abs(sigma) >= 2.0
                          ? 'bg-amber-950 text-amber-300'
                          : 'bg-emerald-950 text-emerald-300'
                      }`}
                    >
                      {sigma > 0 ? `+${sigma.toFixed(2)}` : sigma.toFixed(2)}σ
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    {abnormal.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {abnormal.map((fl) => (
                          <span
                            key={fl}
                            className="rounded bg-rose-600/20 px-1.5 py-0.5 text-[9px] font-semibold text-rose-300 border border-rose-500/30"
                          >
                            {fl}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="flex items-center text-[11px] text-emerald-400 gap-1">
                        <CheckCircle className="h-3 w-3" />
                        <span>Pass</span>
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedSensor(sensorName);
                      }}
                      className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 hover:text-white"
                    >
                      Plot
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
});

