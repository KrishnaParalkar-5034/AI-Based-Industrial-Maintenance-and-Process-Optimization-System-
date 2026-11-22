import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Award,
  ChevronLeft,
  ChevronRight,
  Compass,
  Cpu,
  Layers,
  Radio,
  Search,
  ShieldAlert,
  Sliders,
  Wifi,
  WifiOff,
} from 'lucide-react';

export interface NavItem {
  id: string;
  route: string;
  label: string;
  shortLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number | null;
  badgeColor?: string;
}

export interface NavGroup {
  groupName: string;
  items: NavItem[];
}

interface SidebarProps {
  currentRoute: string;
  onRouteChange: (route: string) => void;
  activeAlarmsCount: number;
  isConnected: boolean;
  latencyMs: number;
  onOpenCommandPalette: () => void;
}

export const Sidebar: React.FC<SidebarProps> = React.memo(({
  currentRoute,
  onRouteChange,
  activeAlarmsCount,
  isConnected,
  latencyMs,
  onOpenCommandPalette,
}) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('tep_sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const toggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('tep_sidebar_collapsed', String(next));
      } catch (e) {
        console.warn('Sidebar state persistence error:', e);
      }
      return next;
    });
  };

  const navGroups: NavGroup[] = [
    {
      groupName: 'MONITORING',
      items: [
        {
          id: 'cockpit',
          route: '/cockpit',
          label: 'Plant Cockpit & P&ID',
          shortLabel: 'Cockpit',
          icon: Compass,
        },
        {
          id: 'telemetry',
          route: '/telemetry',
          label: 'Telemetry Explorer',
          shortLabel: 'Telemetry',
          icon: Radio,
        },
      ],
    },
    {
      groupName: 'INTELLIGENCE',
      items: [
        {
          id: 'diagnostics',
          route: '/diagnostics',
          label: 'AI Diagnostics & XAI',
          shortLabel: 'Diagnostics',
          icon: Cpu,
        },
        {
          id: 'benchmarks',
          route: '/benchmarks',
          label: 'Model Benchmarks',
          shortLabel: 'Benchmarks',
          icon: Award,
        },
      ],
    },
    {
      groupName: 'OPERATIONS',
      items: [
        {
          id: 'alarms',
          route: '/alarms',
          label: 'ISA-18.2 Alarms & Handover',
          shortLabel: 'Alarms',
          icon: AlertTriangle,
          badge: activeAlarmsCount > 0 ? `${activeAlarmsCount} Active` : null,
          badgeColor: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
        },
        {
          id: 'utilities',
          route: '/utilities',
          label: 'Utilities & System Ops',
          shortLabel: 'Utilities',
          icon: Sliders,
        },
      ],
    },
  ];

  return (
    <aside
      className={`relative z-30 flex flex-col border-r border-slate-800/80 bg-[#0a0f1d] text-slate-200 transition-[width] duration-200 ease-out select-none ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Sidebar Header: App Title & Branding */}
      <div className="flex h-14 items-center border-b border-slate-800/80 px-2.5">
        {isCollapsed ? (
          <button
            onClick={toggleCollapse}
            title="Expand sidebar"
            className="group flex h-9 w-full items-center justify-center rounded-lg border border-slate-800 bg-slate-900/80 text-blue-400 hover:border-blue-500/40 hover:bg-blue-600/20 transition"
          >
            <Activity className="h-4 w-4 group-hover:hidden animate-pulse" />
            <ChevronRight className="h-4 w-4 hidden group-hover:block text-white" />
          </button>
        ) : (
          <div className="flex w-full items-center justify-between overflow-hidden">
            <div className="flex items-center space-x-2.5 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/30">
                <Activity className="h-4 w-4 animate-pulse" />
              </div>
              <div className="min-w-0 flex-1 truncate">
                <div className="flex items-center space-x-1.5">
                  <span className="font-bold text-xs tracking-tight text-white uppercase">
                    TEP SCADA AI
                  </span>
                  <span className="rounded bg-blue-900/60 px-1 py-0.2 text-[9px] font-mono text-blue-300">
                    v2.5
                  </span>
                </div>
                <p className="truncate text-[10px] text-slate-400 font-mono">
                  3-Pillar Predictive System
                </p>
              </div>
            </div>

            <button
              onClick={toggleCollapse}
              title="Collapse sidebar"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:text-white transition"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Advisory Badge */}
      <div className="p-2 border-b border-slate-800/60">
        {!isCollapsed ? (
          <div className="flex items-center space-x-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold text-amber-300">
            <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-400" />
            <span className="truncate">ADVISORY MODE — HUMAN-IN-THE-LOOP</span>
          </div>
        ) : (
          <div
            title="ADVISORY MODE — HUMAN-IN-THE-LOOP (Zero Actuation)"
            className="flex h-8 w-full items-center justify-center rounded border border-amber-500/30 bg-amber-500/10 text-amber-400"
          >
            <ShieldAlert className="h-4 w-4" />
          </div>
        )}
      </div>

      {/* Quick Search / Command Palette Button */}
      <div className="p-2">
        <button
          onClick={onOpenCommandPalette}
          className={`flex w-full items-center rounded-lg border border-slate-800 bg-slate-900/80 text-xs text-slate-400 hover:border-slate-700 hover:text-slate-200 transition ${
            isCollapsed ? 'h-9 justify-center' : 'h-8 px-2.5 justify-between'
          }`}
          title="Search pages, P&ID units, sensors, and actions (Ctrl+K)"
        >
          <div className="flex items-center space-x-2">
            <Search className="h-3.5 w-3.5 text-slate-400" />
            {!isCollapsed && <span className="text-[11px]">Command search...</span>}
          </div>
          {!isCollapsed && (
            <kbd className="rounded border border-slate-700 bg-slate-800 px-1.5 py-0.2 text-[9px] font-mono text-slate-400">
              Ctrl+K
            </kbd>
          )}
        </button>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 overflow-y-auto px-2 py-2 space-y-4">
        {navGroups.map((group) => (
          <div key={group.groupName} className="space-y-1">
            {!isCollapsed ? (
              <div className="px-2.5 py-1 text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                {group.groupName}
              </div>
            ) : (
              <div className="my-1 border-t border-slate-800/40" />
            )}

            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive =
                currentRoute === item.route ||
                (item.route === '/cockpit' && currentRoute === '/');

              return (
                <div key={item.id} className="relative group">
                  <button
                    onClick={() => onRouteChange(item.route)}
                    className={`flex w-full items-center rounded-lg transition text-xs font-medium ${
                      isCollapsed
                        ? 'h-10 justify-center'
                        : 'h-9 px-2.5 justify-between'
                    } ${
                      isActive
                        ? 'border border-blue-500/40 bg-blue-600/15 text-blue-300 font-semibold shadow-sm'
                        : 'border border-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5 truncate">
                      <div className="relative flex items-center justify-center shrink-0">
                        <Icon
                          className={`h-4 w-4 shrink-0 transition ${
                            isActive
                              ? 'text-blue-400'
                              : 'text-slate-400 group-hover:text-slate-200'
                          }`}
                        />
                        {isCollapsed && item.badge && (
                          <span className="absolute -top-1.5 -right-2 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-rose-600 px-1 text-[9px] font-mono font-extrabold text-white ring-1 ring-slate-900 shadow-sm animate-pulse">
                            {typeof item.badge === 'string' && item.badge.includes('Active')
                              ? item.badge.split(' ')[0]
                              : item.badge}
                          </span>
                        )}
                      </div>
                      {!isCollapsed && (
                        <span className="truncate">{item.label}</span>
                      )}
                    </div>

                    {!isCollapsed && item.badge && (
                      <span
                        className={`rounded-full border px-1.5 py-0.2 text-[10px] font-mono font-bold ${
                          item.badgeColor ?? 'bg-slate-800 text-slate-300 border-slate-700'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>

                  {/* Tooltip on Collapsed Mode */}
                  {isCollapsed && (
                    <div className="pointer-events-none absolute left-full top-1/2 ml-2 -translate-y-1/2 z-50 hidden rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-white shadow-xl group-hover:flex items-center space-x-2 whitespace-nowrap">
                      <span>{item.label}</span>
                      {item.badge && (
                        <span
                          className={`rounded px-1 text-[9px] font-mono font-bold ${
                            item.badgeColor ?? 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Sidebar Footer: Latency Pill & Connection */}
      <div className="border-t border-slate-800/80 p-2.5 bg-[#090d19]">
        {!isCollapsed ? (
          <div
            className={`flex items-center justify-between rounded-md border px-2.5 py-1.5 font-mono text-[11px] ${
              isConnected
                ? 'border-blue-500/30 bg-blue-500/10 text-blue-300'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
            }`}
          >
            <div className="flex items-center space-x-2">
              {isConnected ? (
                <>
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
                  </span>
                  <span>LIVE WS</span>
                </>
              ) : (
                <>
                  <span className="h-2 w-2 rounded-full bg-rose-500" />
                  <span>OFFLINE</span>
                </>
              )}
            </div>
            <span>{latencyMs.toFixed(1)} ms</span>
          </div>
        ) : (
          <div
            title={`WebSocket: ${isConnected ? `LIVE (${latencyMs.toFixed(1)} ms)` : 'OFFLINE'}`}
            className={`flex h-8 w-full items-center justify-center rounded border ${
              isConnected
                ? 'border-blue-500/30 bg-blue-500/10 text-blue-400'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-400'
            }`}
          >
            {isConnected ? (
              <Wifi className="h-4 w-4" />
            ) : (
              <WifiOff className="h-4 w-4" />
            )}
          </div>
        )}
      </div>
    </aside>
  );
});

