import React, { useCallback, useEffect, useState } from 'react';
import { controlStream, getAlarms, getStreamStatus, reloadModels } from './api';
import { AlarmConsoleView } from './components/AlarmConsoleView';
import { BenchmarksView } from './components/BenchmarksView';
import { CockpitView } from './components/CockpitView';
import { CommandPalette } from './components/CommandPalette';
import { DiagnosticsView } from './components/DiagnosticsView';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { TelemetryExplorerView } from './components/TelemetryExplorerView';
import { UtilitiesView } from './components/UtilitiesView';
import { SENSOR_DETAILS } from './constants';
import { StreamStatusResponse } from './types';
import { useTelemetrySocket } from './useTelemetrySocket';

export function App() {
  // Real browser URL routing
  const [currentRoute, setCurrentRoute] = useState<string>(() => {
    const path = window.location.pathname;
    return path && path !== '/' ? path : '/cockpit';
  });

  const [selectedUnit, setSelectedUnit] = useState<string | null>(null);
  const [selectedSensor, setSelectedSensor] = useState<string | null>(null);
  const [status, setStatus] = useState<StreamStatusResponse | null>(null);
  const [activeAlarmsCount, setActiveAlarmsCount] = useState<number>(0);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isInjectModalOpen, setIsInjectModalOpen] = useState(false);

  // Single permanent root-mounted WebSocket connection
  const { currentFrame, history, isConnected, latencyMs } = useTelemetrySocket();

  // URL sync: listen to popstate
  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      setCurrentRoute(path && path !== '/' ? path : '/cockpit');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleNavigate = useCallback((route: string) => {
    if (window.location.pathname !== route) {
      window.history.pushState({}, '', route);
    }
    setCurrentRoute(route);
  }, []);

  // Status polling for system playback & alarm telemetry
  const refreshStatus = useCallback(async () => {
    try {
      const data = await getStreamStatus();
      setStatus(data);
    } catch (e) {
      console.warn('Status poll deferred:', e);
    }

    try {
      const active = await getAlarms('ACTIVE', undefined, 50);
      setActiveAlarmsCount(active.length);
    } catch (e) {
      if (currentFrame && currentFrame.regime !== 'NORMAL') {
        setActiveAlarmsCount(1);
      }
    }
  }, [currentFrame?.regime]);

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 5000);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  // Global Ctrl+K / Cmd+K hotkey to trigger Command Palette
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Sensor selection helper: maps tag (e.g. 'xmeas_9') to human sensor name
  const handleSelectSensorByTag = useCallback((tagOrName: string) => {
    let foundName: string | null = null;
    if (SENSOR_DETAILS[tagOrName]) {
      foundName = tagOrName;
    } else {
      const entry = Object.entries(SENSOR_DETAILS).find(
        ([, v]) => v.tag.toLowerCase() === tagOrName.toLowerCase()
      );
      if (entry) foundName = entry[0];
    }
    if (foundName) {
      setSelectedSensor(foundName);
    }
  }, []);

  // Quick action executor for Command Palette
  const handleTriggerAction = useCallback(async (actionKey: string) => {
    switch (actionKey) {
      case 'toggle_play':
        try {
          await controlStream({ action: status?.is_playing ? 'pause' : 'play' });
          refreshStatus();
        } catch (e) {
          console.error(e);
        }
        break;
      case 'step_forward':
        try {
          const step = (currentFrame?.step ?? status?.current_step ?? 0) + 1;
          await controlStream({ action: 'seek', step });
          refreshStatus();
        } catch (e) {
          console.error(e);
        }
        break;
      case 'open_fault_inject':
        setIsInjectModalOpen(true);
        break;
      case 'set_mode_stacked_ensemble':
        try {
          await controlStream({ action: 'toggle_mode', model_mode: 'stacked_ensemble' });
          refreshStatus();
        } catch (e) {
          console.error(e);
        }
        break;
      case 'set_mode_xgboost':
        try {
          await controlStream({ action: 'toggle_mode', model_mode: 'xgboost' });
          refreshStatus();
        } catch (e) {
          console.error(e);
        }
        break;
      case 'set_mode_lstm_fcn':
        try {
          await controlStream({ action: 'toggle_mode', model_mode: 'lstm_fcn' });
          refreshStatus();
        } catch (e) {
          console.error(e);
        }
        break;
      case 'set_mode_anomaly':
        try {
          await controlStream({ action: 'toggle_mode', model_mode: 'anomaly' });
          refreshStatus();
        } catch (e) {
          console.error(e);
        }
        break;
      case 'reload_models':
        try {
          await reloadModels();
          alert('Production ML models hot-reloaded successfully.');
          refreshStatus();
        } catch (e: any) {
          alert(`Model reload failed: ${e.message}`);
        }
        break;
      case 'export_handover':
        handleNavigate('/alarms');
        break;
      default:
        console.warn('Unhandled quick action:', actionKey);
    }
  }, [status?.is_playing, status?.current_step, currentFrame?.step, handleNavigate, refreshStatus]);

  const handleOpenInExplorer = useCallback((u: string) => {
    setSelectedUnit(u);
    handleNavigate('/telemetry');
  }, [handleNavigate]);

  const handleCommandSelectUnit = useCallback((u: string) => {
    setSelectedUnit(u);
    handleNavigate('/cockpit');
  }, [handleNavigate]);

  const handleCommandSelectSensor = useCallback((sensorTag: string) => {
    handleSelectSensorByTag(sensorTag);
    handleNavigate('/telemetry');
  }, [handleSelectSensorByTag, handleNavigate]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#080d1a] text-slate-100 font-sans antialiased">
      {/* 1. Left SCADA Navigation Sidebar */}
      <Sidebar
        currentRoute={currentRoute}
        onRouteChange={handleNavigate}
        activeAlarmsCount={activeAlarmsCount}
        isConnected={isConnected}
        latencyMs={latencyMs}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
      />

      {/* 2. Main Workstation Panel */}
      <div className="flex flex-1 flex-col min-w-0 h-full overflow-hidden">
        {/* Slim Contextual Top Bar */}
        <Header
          currentRoute={currentRoute}
          currentFrame={currentFrame}
          status={status}
          onRefreshStatus={refreshStatus}
          isInjectModalOpen={isInjectModalOpen}
          onToggleInjectModal={setIsInjectModalOpen}
        />

        {/* Scrollable View Content Canvas */}
        <main className="flex-1 min-w-0 overflow-y-auto px-5 py-4 bg-[#080d1a]">
          {(currentRoute === '/cockpit' || currentRoute === '/') && (
            <CockpitView
              currentFrame={currentFrame}
              history={history}
              selectedUnit={selectedUnit}
              onSelectUnit={setSelectedUnit}
              onOpenInExplorer={handleOpenInExplorer}
            />
          )}

          {currentRoute === '/telemetry' && (
            <TelemetryExplorerView
              currentFrame={currentFrame}
              history={history}
              selectedUnit={selectedUnit}
              onSelectUnit={setSelectedUnit}
              selectedSensor={selectedSensor}
              onSelectSensor={setSelectedSensor}
            />
          )}

          {currentRoute === '/diagnostics' && (
            <DiagnosticsView currentFrame={currentFrame} />
          )}

          {currentRoute === '/benchmarks' && (
            <BenchmarksView />
          )}

          {currentRoute === '/alarms' && (
            <AlarmConsoleView status={status} onRefreshStatus={refreshStatus} />
          )}

          {currentRoute === '/utilities' && (
            <UtilitiesView />
          )}
        </main>

        {/* Minimal Control-Room Footer */}
        <footer className="h-6 border-t border-slate-800/80 bg-[#070b16] px-3 flex items-center justify-between text-[10px] text-slate-500 font-mono select-none shrink-0">
          <div className="flex items-center space-x-2">
            <span>Tennessee Eastman Process Predictive Maintenance</span>
            <span>•</span>
            <span>Downs & Vogel Benchmark</span>
          </div>
          <div className="flex items-center space-x-2.5">
            <span>Advisory Decision Support</span>
            <span>•</span>
            <span className="text-amber-400/90 font-medium">Zero Physical Actuation Protocol</span>
          </div>
        </footer>
      </div>

      {/* Global Command Palette Modal */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onNavigate={handleNavigate}
        onSelectUnit={handleCommandSelectUnit}
        onSelectSensor={handleCommandSelectSensor}
        onTriggerAction={handleTriggerAction}
      />
    </div>
  );
}

export default App;
