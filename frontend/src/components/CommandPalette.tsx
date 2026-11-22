import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Award,
  Compass,
  Cpu,
  Flame,
  Gauge,
  Layers,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Search,
  Sliders,
  Terminal,
} from 'lucide-react';
import { PID_UNITS, SENSOR_DETAILS } from '../constants';

export interface CommandItem {
  id: string;
  category: 'Pages' | 'P&ID Units' | 'Sensors & Actuators' | 'Quick Actions';
  title: string;
  subtitle?: string;
  tag?: string;
  icon: React.ComponentType<{ className?: string }>;
  action: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (route: string) => void;
  onSelectUnit: (unitName: string) => void;
  onSelectSensor: (sensorTag: string) => void;
  onTriggerAction: (actionKey: string) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onSelectUnit,
  onSelectSensor,
  onTriggerAction,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Global Ctrl+K / Cmd+K listener handled by parent or here
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
      }
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Build the complete command catalogue
  const allCommands = useMemo<CommandItem[]>(() => {
    const items: CommandItem[] = [];

    // 1. Pages (Navigation)
    items.push(
      {
        id: 'nav-cockpit',
        category: 'Pages',
        title: 'Plant Cockpit & P&ID Digital Twin',
        subtitle: 'Real-time 6-vessel SVG schematic, Plant Health Index & Risk Timeline',
        tag: '/cockpit',
        icon: Compass,
        action: () => {
          onNavigate('/cockpit');
          onClose();
        },
      },
      {
        id: 'nav-telemetry',
        category: 'Pages',
        title: 'Telemetry Explorer & Signal Quality',
        subtitle: '52-variable multi-channel trends with ±2σ normal operational bands',
        tag: '/telemetry',
        icon: Radio,
        action: () => {
          onNavigate('/telemetry');
          onClose();
        },
      },
      {
        id: 'nav-diagnostics',
        category: 'Pages',
        title: 'AI Diagnostics & Root Cause XAI',
        subtitle: '21-class fault classification, prescriptive advice & live TreeSHAP waterfall',
        tag: '/diagnostics',
        icon: Cpu,
        action: () => {
          onNavigate('/diagnostics');
          onClose();
        },
      },
      {
        id: 'nav-benchmarks',
        category: 'Pages',
        title: 'Model Benchmarks & Early-Warning Audit',
        subtitle: 'Heterogeneous evaluation matrix with 4-decimal precision & early-warning detection delays',
        tag: '/benchmarks',
        icon: Award,
        action: () => {
          onNavigate('/benchmarks');
          onClose();
        },
      },
      {
        id: 'nav-alarms',
        category: 'Pages',
        title: 'ISA-18.2 Alarms & Shift Handover',
        subtitle: 'Chatter filter, active alarm console, and print-ready handover reports',
        tag: '/alarms',
        icon: AlertTriangle,
        action: () => {
          onNavigate('/alarms');
          onClose();
        },
      },
      {
        id: 'nav-utilities',
        category: 'Pages',
        title: 'Utilities & System Operations',
        subtitle: 'Batch CSV analyzer, audit logs, model hot-reload & database reset',
        tag: '/utilities',
        icon: Sliders,
        action: () => {
          onNavigate('/utilities');
          onClose();
        },
      }
    );

    // 2. P&ID Units
    Object.entries(PID_UNITS).forEach(([unitName, info]) => {
      items.push({
        id: `unit-${unitName}`,
        category: 'P&ID Units',
        title: unitName,
        subtitle: info.description,
        tag: `${info.measuredSensors.length} sensors · ${info.valves.length} valves`,
        icon: Layers,
        action: () => {
          onNavigate('/cockpit');
          onSelectUnit(unitName);
          onClose();
        },
      });
    });

    // 3. Sensors & Manipulated Variables
    Object.entries(SENSOR_DETAILS).forEach(([name, details]) => {
      items.push({
        id: `sensor-${details.tag}`,
        category: 'Sensors & Actuators',
        title: `${details.tag}: ${name}`,
        subtitle: `Unit: ${details.unit} • Nominal span [${details.min} - ${details.max}]`,
        tag: details.tag,
        icon: Gauge,
        action: () => {
          onNavigate('/telemetry');
          onSelectSensor(details.tag);
          onClose();
        },
      });
    });

    // 4. Quick Actions
    items.push(
      {
        id: 'act-play-pause',
        category: 'Quick Actions',
        title: 'Toggle Stream Playback (Play / Pause)',
        subtitle: 'Pause or resume the real-time simulation stream',
        icon: Play,
        action: () => {
          onTriggerAction('toggle_play');
          onClose();
        },
      },
      {
        id: 'act-step',
        category: 'Quick Actions',
        title: 'Step Forward (+1 Sample)',
        subtitle: 'Advance playback by exactly one 3-minute telemetry frame',
        icon: Activity,
        action: () => {
          onTriggerAction('step_forward');
          onClose();
        },
      },
      {
        id: 'act-inject-fault',
        category: 'Quick Actions',
        title: 'Simulate Physical TEP Disturbance...',
        subtitle: 'Open the 21-benchmark fault injection dialog',
        icon: Flame,
        action: () => {
          onTriggerAction('open_fault_inject');
          onClose();
        },
      },
      {
        id: 'act-mode-ensemble',
        category: 'Quick Actions',
        title: 'Set Model: Stacked Heterogeneous Ensemble',
        subtitle: 'Pillar 1 + Pillar 2 + Pillar 3 Meta-Learner (Recommended)',
        icon: Layers,
        action: () => {
          onTriggerAction('set_mode_stacked_ensemble');
          onClose();
        },
      },
      {
        id: 'act-mode-xgboost',
        category: 'Quick Actions',
        title: 'Set Model: Pillar 1 XGBoost Tabular',
        subtitle: 'High-speed gradient boosting on 364 rolling features',
        icon: Cpu,
        action: () => {
          onTriggerAction('set_mode_xgboost');
          onClose();
        },
      },
      {
        id: 'act-mode-lstm',
        category: 'Quick Actions',
        title: 'Set Model: Pillar 2 LSTM-FCN Temporal',
        subtitle: 'Deep sequence modeling over 20-step sliding windows',
        icon: Activity,
        action: () => {
          onTriggerAction('set_mode_lstm_fcn');
          onClose();
        },
      },
      {
        id: 'act-mode-anomaly',
        category: 'Quick Actions',
        title: 'Set Model: Pillar 3 Autoencoder Safety Net',
        subtitle: 'Unsupervised reconstruction MSE for unmodeled anomalies',
        icon: Layers,
        action: () => {
          onTriggerAction('set_mode_anomaly');
          onClose();
        },
      },
      {
        id: 'act-reload-models',
        category: 'Quick Actions',
        title: 'Hot-Reload Production ML Artifacts',
        subtitle: 'Reload weights and meta-learner without restarting backend',
        icon: RefreshCw,
        action: () => {
          onTriggerAction('reload_models');
          onClose();
        },
      },
      {
        id: 'act-export-handover',
        category: 'Quick Actions',
        title: 'Export Shift Handover Report',
        subtitle: 'Generate and review print-ready handover documentation',
        icon: Terminal,
        action: () => {
          onNavigate('/alarms');
          onTriggerAction('export_handover');
          onClose();
        },
      }
    );

    return items;
  }, [onNavigate, onSelectUnit, onSelectSensor, onTriggerAction, onClose]);

  // Filter commands by search query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) return allCommands.slice(0, 30);
    const q = query.toLowerCase().trim();
    return allCommands.filter((item) => {
      const matchTitle = item.title.toLowerCase().includes(q);
      const matchSubtitle = item.subtitle?.toLowerCase().includes(q);
      const matchTag = item.tag?.toLowerCase().includes(q);
      const matchCat = item.category.toLowerCase().includes(q);
      return matchTitle || matchSubtitle || matchTag || matchCat;
    });
  }, [allCommands, query]);

  // Keep selected index within bounds
  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredCommands]);

  // Keyboard navigation inside modal
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (filteredCommands.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % filteredCommands.length);
      scrollItemIntoView((selectedIndex + 1) % filteredCommands.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) =>
        prev === 0 ? filteredCommands.length - 1 : prev - 1
      );
      scrollItemIntoView(
        selectedIndex === 0 ? filteredCommands.length - 1 : selectedIndex - 1
      );
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const current = filteredCommands[selectedIndex];
      if (current) current.action();
    }
  };

  const scrollItemIntoView = (index: number) => {
    const list = listRef.current;
    if (!list) return;
    const items = list.getElementsByTagName('button');
    if (items[index]) {
      items[index].scrollIntoView({ block: 'nearest' });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/75 backdrop-blur-sm animate-in fade-in duration-100">
      <div
        className="w-full max-w-2xl overflow-hidden rounded-xl border border-slate-700/80 bg-[#0c1427] shadow-2xl transition-all"
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center border-b border-slate-800 px-4 py-3">
          <Search className="h-5 w-5 text-slate-400 mr-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages, P&ID units, sensors (e.g. xmeas_9), or actions..."
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 outline-none font-sans"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="text-xs text-slate-500 hover:text-slate-300 font-mono px-1"
            >
              Clear
            </button>
          )}
          <kbd className="ml-2 rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-400">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div
          ref={listRef}
          className="max-h-[380px] overflow-y-auto p-2 divide-y divide-slate-800/40"
        >
          {filteredCommands.length > 0 ? (
            filteredCommands.map((cmd, idx) => {
              const Icon = cmd.icon;
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={cmd.id}
                  onClick={() => cmd.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition ${
                    isSelected
                      ? 'bg-blue-600/20 text-white border border-blue-500/30'
                      : 'text-slate-300 hover:bg-slate-800/50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center space-x-3 min-w-0 flex-1 mr-2">
                    <div
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
                        isSelected
                          ? 'border-blue-400 bg-blue-600/30 text-blue-300'
                          : 'border-slate-800 bg-slate-900 text-slate-400'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1 truncate">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-xs truncate">
                          {cmd.title}
                        </span>
                        <span className="rounded bg-slate-800/80 px-1.5 py-0.2 text-[9px] font-mono text-slate-400">
                          {cmd.category}
                        </span>
                      </div>
                      {cmd.subtitle && (
                        <p className="truncate text-[11px] text-slate-400">
                          {cmd.subtitle}
                        </p>
                      )}
                    </div>
                  </div>

                  {cmd.tag && (
                    <span className="shrink-0 font-mono text-[10px] text-slate-400 rounded bg-slate-800/60 px-2 py-0.5 border border-slate-700/60">
                      {cmd.tag}
                    </span>
                  )}
                </button>
              );
            })
          ) : (
            <div className="py-12 text-center text-xs text-slate-400 font-mono">
              No results found for &quot;{query}&quot;. Try &quot;reactor&quot;, &quot;xmeas_9&quot;, or &quot;benchmarks&quot;.
            </div>
          )}
        </div>

        {/* Modal Footer Keybinds */}
        <div className="flex items-center justify-between border-t border-slate-800 bg-[#090e1a] px-4 py-2 text-[11px] text-slate-400 font-mono">
          <div className="flex items-center space-x-3">
            <span><kbd className="rounded bg-slate-800 px-1 text-[10px]">↑</kbd> <kbd className="rounded bg-slate-800 px-1 text-[10px]">↓</kbd> Navigate</span>
            <span><kbd className="rounded bg-slate-800 px-1 text-[10px]">↵</kbd> Select</span>
            <span><kbd className="rounded bg-slate-800 px-1 text-[10px]">ESC</kbd> Close</span>
          </div>
          <span className="text-slate-500">
            {filteredCommands.length} command{filteredCommands.length === 1 ? '' : 's'} available
          </span>
        </div>
      </div>
    </div>
  );
};
