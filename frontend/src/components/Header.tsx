import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  FastForward,
  Flame,
  Pause,
  Play,
  RotateCcw,
  SkipForward,
} from 'lucide-react';
import { controlStream } from '../api';
import { TEP_FAULTS } from '../constants';
import { StreamStatusResponse, TelemetryFrame } from '../types';

interface HeaderProps {
  currentRoute: string;
  currentFrame: TelemetryFrame | null;
  status: StreamStatusResponse | null;
  onRefreshStatus: () => void;
  isInjectModalOpen: boolean;
  onToggleInjectModal: (open: boolean) => void;
}

export const Header: React.FC<HeaderProps> = React.memo(({
  currentRoute,
  currentFrame,
  status,
  onRefreshStatus,
  isInjectModalOpen,
  onToggleInjectModal,
}) => {
  const [selectedFaultId, setSelectedFaultId] = useState<number>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedModeOverride, setFeedModeOverride] = useState<'replay' | 'simulator' | null>(null);

  const isPlaying = status?.is_playing ?? false;
  const currentStep = currentFrame?.step ?? status?.current_step ?? 0;
  const totalSteps = currentFrame?.total_steps ?? status?.total_steps ?? 500;
  const speed = status?.speed ?? 1.0;
  const availableRuns = status?.available_runs ?? ['LIVE_STREAM'];
  const activeMode = currentFrame?.model_mode ?? status?.active_model_mode ?? 'stacked_ensemble';
  const sensorHealth = currentFrame?.sensor_health_score ?? 100.0;
  const activeFaultId = currentFrame?.active_fault ?? status?.active_fault_id ?? 0;

  const isLiveSim = feedModeOverride !== null
    ? feedModeOverride === 'simulator'
    : (status?.adapter_type === 'simulator' || status?.current_run_id === 'LIVE_STREAM' || currentFrame?.run_id === 'LIVE_STREAM');

  const currentRun = isLiveSim
    ? 'LIVE_STREAM'
    : (status?.current_run_id && status.current_run_id !== 'LIVE_STREAM'
        ? status.current_run_id
        : (currentFrame?.run_id ?? 'F00_R09'));

  React.useEffect(() => {
    if (status?.adapter_type) {
      setFeedModeOverride(status.adapter_type as 'replay' | 'simulator');
    }
  }, [status?.adapter_type, status?.current_run_id]);

  const isLiveStreamRoute =
    currentRoute === '/cockpit' ||
    currentRoute === '/' ||
    currentRoute === '/telemetry' ||
    currentRoute === '/diagnostics' ||
    currentRoute === '/alarms';

  const routeTitles: Record<string, string> = {
    '/cockpit': 'Cockpit & P&ID',
    '/': 'Cockpit & P&ID',
    '/telemetry': 'Telemetry Explorer',
    '/diagnostics': 'AI Diagnostics & XAI',
    '/benchmarks': 'Model Benchmarks',
    '/alarms': 'Alarms & Handover',
    '/utilities': 'Utilities & System Ops',
  };

  const currentTitle = routeTitles[currentRoute] ?? 'Industrial AI Control Room';

  // Playback handlers
  const handleTogglePlay = async () => {
    try {
      if (!isPlaying && currentStep >= totalSteps - 1) {
        await controlStream({ action: 'seek', step: 0 });
      }
      await controlStream({ action: isPlaying ? 'pause' : 'play' });
      onRefreshStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStepForward = async () => {
    try {
      await controlStream({ action: 'seek', step: currentStep + 1 });
      onRefreshStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSpeedChange = async (newSpeed: number) => {
    try {
      await controlStream({ action: 'speed', speed: newSpeed });
      onRefreshStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSeek = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const targetStep = parseInt(e.target.value, 10);
    try {
      await controlStream({ action: 'seek', step: targetStep });
      onRefreshStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const runId = e.target.value;
    try {
      await controlStream({ action: 'switch_run', run_id: runId });
      onRefreshStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const handleModeChange = async (mode: string) => {
    try {
      await controlStream({ action: 'toggle_mode', model_mode: mode });
      onRefreshStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleFeed = async (feedType: 'replay' | 'simulator') => {
    setFeedModeOverride(feedType);
    try {
      await controlStream({ action: 'switch_adapter', adapter_type: feedType });
      onRefreshStatus();
    } catch (err) {
      console.error(err);
      setFeedModeOverride(null);
    }
  };

  const handleInjectFault = async () => {
    setIsSubmitting(true);
    try {
      await controlStream({ action: 'inject_fault', fault_id: selectedFaultId });
      setFeedModeOverride('simulator');
      onToggleInjectModal(false);
      onRefreshStatus();
    } catch (err: any) {
      alert(`Fault injection failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClearFault = async () => {
    try {
      await controlStream({ action: 'inject_fault', fault_id: 0 });
      onRefreshStatus();
    } catch (err: any) {
      console.error('Failed to clear fault:', err);
    }
  };

  // Anomaly tag count excluding HEALTHY / OK
  const flaggedCount = currentFrame?.channel_flags
    ? Object.values(currentFrame.channel_flags).filter(
        (flags) =>
          Array.isArray(flags) && flags.some((f) => f !== 'HEALTHY' && f !== 'OK')
      ).length
    : 0;

  return (
    <header className="h-14 border-b border-slate-800/80 bg-[#0b1324] px-2.5 sm:px-3 flex items-center justify-between text-slate-100 shadow-sm shrink-0 z-20 min-w-0 overflow-x-hidden">
      {/* Left: Active Page Title & Live Sample Step Context */}
      <div className="flex items-center space-x-2.5 min-w-0 shrink-0">
        <h1 className="text-sm font-bold tracking-tight text-white whitespace-nowrap font-sans">
          {currentTitle}
        </h1>

        {isLiveStreamRoute && (
          <div className="hidden sm:flex items-center rounded-full border border-slate-800 bg-slate-900/90 px-2.5 py-0.5 text-[11px] font-mono text-slate-400 shrink-0">
            {isLiveSim ? (
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-emerald-300 font-semibold tracking-wide">LIVE</span>
                <span>
                  t=<strong className="text-amber-400 tabular-nums">{currentStep}</strong>
                </span>
              </span>
            ) : (
              <span>
                t=<strong className="text-blue-400 tabular-nums">{currentStep}</strong>
                <span className="text-slate-500">/{totalSteps}</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Right: Live Telemetry Controls (Shown strictly on live-stream routes) */}
      {isLiveStreamRoute ? (
        <div className="flex items-center space-x-1 sm:space-x-1.5 text-xs shrink-0 min-w-0">
          {/* Replay / Live Sim Pill */}
          <div className="hidden sm:flex rounded border border-slate-700/80 bg-slate-900/90 p-0.5 shrink-0 whitespace-nowrap">
            <button
              onClick={() => handleToggleFeed('replay')}
              title="Replay held-out TEP runs with time scrubbing"
              className={`rounded px-2 py-0.5 text-[10px] font-semibold transition shrink-0 whitespace-nowrap ${
                !isLiveSim
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Replay
            </button>
            <button
              onClick={() => handleToggleFeed('simulator')}
              title="Continuous live AR(1) plant simulation with on-demand fault injection"
              className={`rounded px-2 py-0.5 text-[10px] font-semibold transition shrink-0 whitespace-nowrap flex items-center gap-1 ${
                isLiveSim
                  ? 'bg-amber-600 text-white shadow-sm font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {isLiveSim && (
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-300 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-300" />
                </span>
              )}
              Live Sim
            </button>
          </div>

          {/* Run Dropdown */}
          <select
            value={currentRun}
            onChange={handleRunChange}
            disabled={isLiveSim}
            className={`hidden md:block max-w-[110px] xl:max-w-[130px] rounded border border-slate-700/80 bg-slate-800/90 px-1.5 py-1 text-[11px] font-mono outline-none hover:border-slate-600 focus:border-blue-500 shrink-0 truncate ${
              isLiveSim
                ? 'text-amber-300 border-amber-600/40 bg-slate-900/90 cursor-default'
                : 'text-slate-200'
            }`}
          >
            {isLiveSim ? (
              <option value="LIVE_STREAM">LIVE_STREAM</option>
            ) : (
              availableRuns.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))
            )}
          </select>

          {/* Model Selector */}
          <select
            value={activeMode}
            onChange={(e) => handleModeChange(e.target.value)}
            className="hidden xl:block max-w-[115px] 2xl:max-w-[135px] rounded border border-slate-700/80 bg-slate-800/90 px-1.5 py-1 text-[10px] xl:text-[11px] font-medium text-slate-200 outline-none hover:border-slate-600 focus:border-blue-500 shrink-0 truncate"
          >
            <option value="stacked_ensemble">★ Ensemble</option>
            <option value="xgboost">P1: XGBoost</option>
            <option value="lstm_fcn">P2: LSTM-FCN</option>
            <option value="anomaly">P3: Safety Net</option>
          </select>

          {/* Time Scrubber */}
          <div className="hidden sm:flex items-center space-x-1 w-14 lg:w-16 xl:w-20 shrink-0">
            <input
              type="range"
              min={0}
              max={Math.max(1, totalSteps - 1)}
              value={currentStep}
              onChange={handleSeek}
              className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-slate-700 accent-blue-500 hover:bg-slate-600"
            />
          </div>

          {/* Speed Buttons */}
          <div className="hidden xl:flex items-center rounded border border-slate-800 bg-slate-900/60 p-0.5 text-[9px] shrink-0 whitespace-nowrap">
            {[1.0, 2.0, 5.0].map((s) => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s)}
                className={`px-1 py-0.5 rounded transition shrink-0 ${
                  speed === s
                    ? 'bg-slate-700 font-bold text-blue-400'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Step Button */}
          <button
            onClick={handleStepForward}
            title="Step Forward (+1 sample)"
            className="flex h-7 w-7 items-center justify-center rounded border border-slate-700/80 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition shrink-0"
          >
            <SkipForward className="h-3.5 w-3.5" />
          </button>

          {/* Play / Pause Button */}
          <button
            onClick={handleTogglePlay}
            className={`flex items-center space-x-1 rounded px-2 py-1 text-xs font-semibold transition shrink-0 whitespace-nowrap ${
              isPlaying
                ? 'bg-amber-600 hover:bg-amber-500 text-white'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm'
            }`}
          >
            {isPlaying ? (
              <>
                <Pause className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{isLiveSim ? 'Pause' : 'Pause'}</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{isLiveSim ? 'Live' : 'Stream'}</span>
              </>
            )}
          </button>

          {/* Active Fault Badge & Clear Control (Live Sim) */}
          {isLiveSim && activeFaultId > 0 && (
            <div className="flex items-center space-x-1 rounded-full border border-amber-500/60 bg-amber-500/20 px-2 py-0.5 text-[11px] font-semibold text-amber-200 shrink-0 shadow-sm animate-pulse">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-400" />
              </span>
              <span>Fault #{activeFaultId}</span>
              <button
                onClick={handleClearFault}
                title="Clear injected fault and recover plant to normal operation"
                className="ml-0.5 rounded bg-amber-600/60 hover:bg-amber-500 px-1 text-[10px] text-white transition font-bold"
              >
                × Clear
              </button>
            </div>
          )}

          {/* Fault Injection Button */}
          <button
            onClick={() => onToggleInjectModal(true)}
            className={`flex items-center space-x-1 rounded border px-1.5 py-1 text-xs font-medium transition shrink-0 whitespace-nowrap ${
              isLiveSim
                ? 'border-amber-500/60 bg-amber-500/20 text-amber-200 hover:bg-amber-500/30 ring-1 ring-amber-500/30'
                : 'border-rose-600/40 bg-rose-600/10 text-rose-300 hover:bg-rose-600/20'
            }`}
            title={isLiveSim ? "Inject dynamic disturbance into live AR(1) plant simulation" : "Inject physical disturbance (switches to live simulator)"}
          >
            <Flame className={`h-3.5 w-3.5 ${isLiveSim ? 'text-amber-400' : 'text-rose-400'}`} />
            <span className="hidden lg:inline">Inject</span>
          </button>

          {/* Signal Quality Indicator */}
          <div
            className={`flex items-center space-x-1 rounded border px-1.5 sm:px-2 py-0.5 font-mono text-[10px] xl:text-[11px] shrink-0 whitespace-nowrap ${
              sensorHealth >= 95
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : sensorHealth >= 80
                ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
            }`}
            title={
              flaggedCount > 0
                ? `${flaggedCount} sensors flagged with dropouts or freeze anomalies`
                : 'All 52 telemetry channels passing quality checks'
            }
          >
            <span
              className={`h-2 w-2 rounded-full ${
                sensorHealth >= 95 ? 'bg-emerald-400' : 'bg-amber-400 animate-ping'
              }`}
            />
            <span className="hidden lg:inline">Sig: </span>
            <span>{sensorHealth.toFixed(1)}%</span>
            {flaggedCount > 0 ? (
              <span className="rounded bg-rose-950/80 px-1 text-[9px] text-rose-200 font-bold">
                {flaggedCount}F
              </span>
            ) : (
              <span className="rounded bg-emerald-950/80 px-1 text-[9px] text-emerald-300 font-bold">
                0F
              </span>
            )}
          </div>
        </div>
      ) : (
        /* Static View Context */
        <div className="flex items-center space-x-2 text-xs text-slate-400 font-mono shrink-0 whitespace-nowrap">
          <span className="rounded border border-slate-800 bg-slate-900/60 px-2.5 py-1">
            Historical & Offline Ops Mode
          </span>
        </div>
      )}

      {/* Fault Injection Modal */}
      {isInjectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2 text-rose-400 font-bold">
                <Flame className="h-5 w-5" />
                <span>Simulate Physical TEP Disturbance</span>
              </div>
              <button
                onClick={() => onToggleInjectModal(false)}
                className="text-slate-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            <div className="py-4 space-y-3">
              <p className="text-xs text-slate-300">
                Select from the 21 benchmark Tennessee Eastman Process fault modes to dynamically inject into the live simulator:
              </p>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Fault Mode (1 - 21)
                </label>
                <select
                  value={selectedFaultId}
                  onChange={(e) => setSelectedFaultId(parseInt(e.target.value, 10))}
                  className="w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-100 outline-none focus:border-rose-500"
                >
                  {Object.entries(TEP_FAULTS)
                    .filter(([id]) => id !== '0')
                    .map(([id, name]) => (
                      <option key={id} value={id}>
                        Fault #{id}: {name}
                      </option>
                    ))}
                </select>
              </div>

              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-300/90">
                <p className="font-semibold flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Real Disturbance Physics
                </p>
                <p className="text-[11px] mt-1 text-slate-400">
                  Fault will ramp over 35 samples (~105 min) across affected sensor and valve channels. The 3-pillar ensemble and ISA-18.2 engine will track propagation.
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-2 border-t border-slate-800 pt-3">
              <button
                onClick={() => onToggleInjectModal(false)}
                className="rounded px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleInjectFault}
                disabled={isSubmitting}
                className="rounded bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-rose-500 transition disabled:opacity-50"
              >
                {isSubmitting ? 'Injecting...' : 'Confirm Injection'}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
});

