import React from 'react';
import { PID_UNITS } from '../constants';
import { TelemetryFrame } from '../types';

interface PidDigitalTwinProps {
  currentFrame: TelemetryFrame | null;
  selectedUnit: string | null;
  onSelectUnit: (unitName: string | null) => void;
}

export const PidDigitalTwin: React.FC<PidDigitalTwinProps> = React.memo(({
  currentFrame,
  selectedUnit,
  onSelectUnit,
}) => {
  const attributions = currentFrame?.unit_attributions_pct ?? {};
  const primaryUnit = currentFrame?.prescriptive_actions?.primary_unit ?? 'None';
  const readings = currentFrame?.readings ?? {};
  const riskScore = currentFrame?.risk_score ?? 0.0;
  const regime = currentFrame?.regime ?? 'NORMAL';

  // Color generator based on effective unit risk (risk_score * shap_share)
  // Ensures vessels stay calm nominal slate/blue during NORMAL regime
  const getUnitTheme = (unitName: string) => {
    const pct = attributions[unitName] ?? 0;
    const isSelected = selectedUnit === unitName;
    const isPlantElevated = regime !== 'NORMAL' || riskScore >= 0.50;
    const effectiveRisk = riskScore * (pct / 100);
    const isPrimary = primaryUnit === unitName && isPlantElevated && pct > 15;

    let stroke = '#334155';
    let fill = '#0f172a';
    let text = '#94a3b8';
    let badgeBg = '#1e293b';
    let badgeText = '#cbd5e1';

    if (isPlantElevated && (effectiveRisk >= 0.20 || (regime === 'CRITICAL' && pct >= 25))) {
      stroke = '#ef4444';
      fill = 'rgba(239, 68, 68, 0.18)';
      text = '#fca5a5';
      badgeBg = '#7f1d1d';
      badgeText = '#fee2e2';
    } else if (isPlantElevated && (effectiveRisk >= 0.10 || (regime === 'WARNING' && pct >= 20))) {
      stroke = '#f59e0b';
      fill = 'rgba(245, 158, 11, 0.15)';
      text = '#fcd34d';
      badgeBg = '#78350f';
      badgeText = '#fef3c7';
    } else if (pct >= 5) {
      stroke = '#3b82f6';
      fill = 'rgba(59, 130, 246, 0.12)';
      text = '#93c5fd';
      badgeBg = '#1e3a8a';
      badgeText = '#dbeafe';
    }

    if (isSelected) {
      stroke = '#38bdf8';
    }

    return { stroke, fill, text, badgeBg, badgeText, pct, isPrimary, isSelected };
  };

  // Adaptive Level Scaling:
  // In real TEP datasets, levels (xmeas_8, xmeas_12, xmeas_15) are natively percentage [0, 100]%.
  // In synthetic/unscaled variants, raw values exceed 100.0 (e.g. ~120.05, ~139.93).
  // If val > 100.0, adaptively rescale against synthetic baseline; otherwise render direct percentage clamped to [0.0, 100.0].
  const clampLevel = (val: number | undefined, syntheticBaseline: number, defaultPct: number) => {
    if (val === undefined || isNaN(val)) return defaultPct.toFixed(1);
    let pct: number;
    if (val > 100.0) {
      pct = (val / (syntheticBaseline || 100.0)) * defaultPct;
    } else {
      pct = val;
    }
    return Math.max(0.0, Math.min(100.0, pct)).toFixed(1);
  };

  const rxTemp = readings['Reactor Temperature']?.toFixed(1) ?? '120.4';
  const rxPress = readings['Reactor Pressure']?.toFixed(0) ?? '2705';
  const rxLevel = clampLevel(readings['Reactor Level'], 120.05, 75.0);
  const sepTemp = readings['Separator Temperature']?.toFixed(1) ?? '80.2';
  const sepLevel = clampLevel(readings['Separator Level'], 139.93, 50.0);
  const strpTemp = readings['Stripper Temperature']?.toFixed(1) ?? '65.8';
  const strpLevel = clampLevel(readings['Stripper Level'], 72.19, 50.0);
  const compWork = readings['Compressor Work']?.toFixed(0) ?? '341';

  return (
    <div className="relative rounded-xl border border-slate-800 bg-[#090e1a] p-3.5 shadow-xl">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold tracking-wide text-slate-100 flex items-center gap-2">
            <span>P&ID Digital Twin & Causal Unit Attribution</span>
            {selectedUnit && (
              <span className="rounded bg-sky-950 px-2 py-0.5 text-xs text-sky-300 font-mono">
                Filtered: {selectedUnit}
              </span>
            )}
          </h2>
          <p className="text-[11px] text-slate-400">
            Interactive Tennessee Eastman plant topology. Dynamic unit coloring driven by real-time TreeSHAP contributions.
          </p>
        </div>
        {selectedUnit && (
          <button
            onClick={() => onSelectUnit(null)}
            className="rounded border border-slate-700 bg-slate-800/80 px-2 py-1 text-xs text-slate-300 hover:text-white"
          >
            Clear Filter
          </button>
        )}
      </div>

      {/* SVG Canvas */}
      <div className="w-full overflow-x-auto">
        <svg
          viewBox="0 0 960 445"
          className="w-full min-w-[720px] select-none font-sans max-h-[415px]"
          style={{ maxHeight: '415px' }}
        >
          <defs>
            {/* Pipe Flow Animation Style */}
            <style>
              {`
                @keyframes pipeFlow {
                  from { stroke-dashoffset: 24; }
                  to { stroke-dashoffset: 0; }
                }
                .flow-pipe {
                  stroke-dasharray: 6 6;
                  animation: pipeFlow 1.6s linear infinite;
                  will-change: stroke-dashoffset;
                }
                .recycle-pipe {
                  stroke-dasharray: 6 6;
                  animation: pipeFlow 2.0s linear infinite;
                  will-change: stroke-dashoffset;
                }
              `}
            </style>
            {/* Arrow Marker */}
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="5"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
            </marker>
            <marker
              id="arrow-recycle"
              viewBox="0 0 10 10"
              refX="5"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
            </marker>
          </defs>

          {/* ============================================================== */}
          {/* PROCESS PIPING & CONNECTING FLOWS                              */}
          {/* ============================================================== */}
          {/* 1. Feed System -> Reactor */}
          <path
            d="M 175 220 L 265 220"
            fill="none"
            stroke="#475569"
            strokeWidth="3"
            markerEnd="url(#arrow)"
          />
          <path
            d="M 175 220 L 265 220"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2"
            className="flow-pipe"
          />

          {/* 2. Reactor -> Product Condenser */}
          <path
            d="M 390 180 L 440 180 L 440 130 L 475 130"
            fill="none"
            stroke="#475569"
            strokeWidth="3"
            markerEnd="url(#arrow)"
          />
          <path
            d="M 390 180 L 440 180 L 440 130 L 475 130"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2"
            className="flow-pipe"
          />

          {/* 3. Product Condenser -> Vapor-Liquid Separator */}
          <path
            d="M 585 130 L 620 130 L 620 190 L 655 190"
            fill="none"
            stroke="#475569"
            strokeWidth="3"
            markerEnd="url(#arrow)"
          />
          <path
            d="M 585 130 L 620 130 L 620 190 L 655 190"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2"
            className="flow-pipe"
          />

          {/* 4. Separator Bottoms (Liquid) -> Product Stripper */}
          <path
            d="M 710 320 L 710 360 L 785 360 L 785 280 L 815 280"
            fill="none"
            stroke="#475569"
            strokeWidth="3"
            markerEnd="url(#arrow)"
          />
          <path
            d="M 710 320 L 710 360 L 785 360 L 785 280 L 815 280"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2"
            className="flow-pipe"
          />

          {/* 5. Separator Overhead Vapor Split:
                 Branch A -> Off-gas Purge (back to Feed/Purge)
                 Branch B -> Overhead vapor to Recycle Compressor suction */}
          <path
            d="M 710 140 L 710 75 L 150 75 L 150 145"
            fill="none"
            stroke="#475569"
            strokeWidth="2.5"
            markerEnd="url(#arrow)"
          />
          <path
            d="M 710 140 L 710 75 L 150 75 L 150 145"
            fill="none"
            stroke="#f59e0b"
            strokeWidth="1.5"
            className="flow-pipe"
          />

          {/* Overhead vapor split line to Recycle Compressor suction */}
          <path
            d="M 710 100 L 760 100 L 760 400 L 545 400"
            fill="none"
            stroke="#475569"
            strokeWidth="2.5"
            markerEnd="url(#arrow)"
          />
          <path
            d="M 710 100 L 760 100 L 760 400 L 545 400"
            fill="none"
            stroke="#a855f7"
            strokeWidth="1.5"
            className="recycle-pipe"
          />

          {/* 6. Recycle Compressor -> Reactor Loop */}
          <path
            d="M 445 400 L 330 400 L 330 340"
            fill="none"
            stroke="#475569"
            strokeWidth="3"
            markerEnd="url(#arrow-recycle)"
          />
          <path
            d="M 445 400 L 330 400 L 330 340"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2"
            className="recycle-pipe"
          />

          {/* Stripper Bottoms (Final Product Stream G & H) */}
          <path
            d="M 870 380 L 870 430 L 930 430"
            fill="none"
            stroke="#10b981"
            strokeWidth="3"
            markerEnd="url(#arrow)"
          />

          {/* ============================================================== */}
          {/* UNIT 1: FEED & PURGE SYSTEM                                    */}
          {/* ============================================================== */}
          {(() => {
            const t = getUnitTheme('Feed & Purge System');
            return (
              <g
                className="cursor-pointer transition-all duration-300"
                onClick={() => onSelectUnit('Feed & Purge System')}
              >
                <rect
                  x="45"
                  y="145"
                  width="130"
                  height="165"
                  rx="10"
                  fill={t.fill}
                  stroke={t.stroke}
                  strokeWidth={t.isSelected ? 3 : 2}
                  className="hover:stroke-sky-400"
                />
                <text x="110" y="170" fill={t.text} fontSize="12" fontWeight="bold" textAnchor="middle">
                  Feed & Purge
                </text>
                <text x="110" y="185" fill="#64748b" fontSize="9" textAnchor="middle">
                  Unit 1 (A/D/E/C Feeds)
                </text>

                {/* Valve representation symbols inside Feed */}
                <circle cx="80" cy="210" r="8" fill="#1e293b" stroke="#64748b" strokeWidth="1.5" />
                <text x="80" y="213" fill="#cbd5e1" fontSize="8" textAnchor="middle">A</text>
                <circle cx="110" cy="210" r="8" fill="#1e293b" stroke="#64748b" strokeWidth="1.5" />
                <text x="110" y="213" fill="#cbd5e1" fontSize="8" textAnchor="middle">D</text>
                <circle cx="140" cy="210" r="8" fill="#1e293b" stroke="#64748b" strokeWidth="1.5" />
                <text x="140" y="213" fill="#cbd5e1" fontSize="8" textAnchor="middle">E</text>

                {/* SHAP Attribution Badge */}
                <rect x="65" y="270" width="90" height="22" rx="4" fill={t.badgeBg} />
                <text x="110" y="285" fill={t.badgeText} fontSize="10" fontWeight="bold" textAnchor="middle">
                  SHAP: {t.pct.toFixed(1)}%
                </text>
              </g>
            );
          })()}

          {/* ============================================================== */}
          {/* UNIT 2: REACTOR                                                */}
          {/* ============================================================== */}
          {(() => {
            const t = getUnitTheme('Reactor');
            return (
              <g
                className="cursor-pointer transition-all duration-300"
                onClick={() => onSelectUnit('Reactor')}
              >
                {/* Reactor Outer Jacket */}
                <rect
                  x="265"
                  y="130"
                  width="125"
                  height="210"
                  rx="24"
                  fill={t.fill}
                  stroke={t.stroke}
                  strokeWidth={t.isSelected ? 3 : 2}
                  className="hover:stroke-sky-400"
                />
                {/* Agitator shaft */}
                <line x1="327" y1="115" x2="327" y2="280" stroke="#64748b" strokeWidth="2.5" />
                <rect x="317" y="105" width="20" height="12" rx="2" fill="#475569" />
                {/* Impellers */}
                <path d="M 310 240 L 345 240 M 310 270 L 345 270" stroke="#94a3b8" strokeWidth="3" />

                <text x="327" y="160" fill={t.text} fontSize="13" fontWeight="bold" textAnchor="middle">
                  Reactor
                </text>
                <text x="327" y="175" fill="#64748b" fontSize="9" textAnchor="middle">
                  Unit 2 (Exothermic)
                </text>

                {/* Telemetry readouts split to left & right of agitator shaft */}
                <text x="296" y="202" fill="#e2e8f0" fontSize="9" textAnchor="middle">
                  {rxTemp} °C
                </text>
                <text x="296" y="216" fill="#94a3b8" fontSize="8" textAnchor="middle">
                  {rxPress} kPa
                </text>
                <text x="358" y="202" fill="#38bdf8" fontSize="9" textAnchor="middle">
                  Level
                </text>
                <text x="358" y="216" fill="#e2e8f0" fontSize="9" textAnchor="middle">
                  {rxLevel}%
                </text>

                {/* SHAP Attribution Badge */}
                <rect x="282" y="300" width="90" height="22" rx="4" fill={t.badgeBg} />
                <text x="327" y="315" fill={t.badgeText} fontSize="10" fontWeight="bold" textAnchor="middle">
                  SHAP: {t.pct.toFixed(1)}%
                </text>
              </g>
            );
          })()}

          {/* ============================================================== */}
          {/* UNIT 3: PRODUCT CONDENSER                                      */}
          {/* ============================================================== */}
          {(() => {
            const t = getUnitTheme('Product Condenser');
            return (
              <g
                className="cursor-pointer transition-all duration-300"
                onClick={() => onSelectUnit('Product Condenser')}
              >
                <rect
                  x="475"
                  y="85"
                  width="110"
                  height="90"
                  rx="12"
                  fill={t.fill}
                  stroke={t.stroke}
                  strokeWidth={t.isSelected ? 3 : 2}
                  className="hover:stroke-sky-400"
                />
                <text x="530" y="110" fill={t.text} fontSize="11" fontWeight="bold" textAnchor="middle">
                  Condenser
                </text>
                <text x="530" y="123" fill="#64748b" fontSize="9" textAnchor="middle">
                  Unit 3 (Cooling)
                </text>
                {/* Shell and tube coil lines */}
                <path d="M 490 135 Q 530 145 570 135" fill="none" stroke="#64748b" strokeWidth="1.5" />
                <path d="M 490 142 Q 530 152 570 142" fill="none" stroke="#64748b" strokeWidth="1.5" />

                <rect x="485" y="150" width="90" height="18" rx="4" fill={t.badgeBg} />
                <text x="530" y="163" fill={t.badgeText} fontSize="10" fontWeight="bold" textAnchor="middle">
                  SHAP: {t.pct.toFixed(1)}%
                </text>
              </g>
            );
          })()}

          {/* ============================================================== */}
          {/* UNIT 4: VAPOR-LIQUID SEPARATOR                                 */}
          {/* ============================================================== */}
          {(() => {
            const t = getUnitTheme('Vapor-Liquid Separator');
            return (
              <g
                className="cursor-pointer transition-all duration-300"
                onClick={() => onSelectUnit('Vapor-Liquid Separator')}
              >
                <rect
                  x="655"
                  y="140"
                  width="110"
                  height="180"
                  rx="22"
                  fill={t.fill}
                  stroke={t.stroke}
                  strokeWidth={t.isSelected ? 3 : 2}
                  className="hover:stroke-sky-400"
                />
                <text x="710" y="170" fill={t.text} fontSize="12" fontWeight="bold" textAnchor="middle">
                  V-L Separator
                </text>
                <text x="710" y="185" fill="#64748b" fontSize="9" textAnchor="middle">
                  Unit 4 (Flash Knockout)
                </text>

                {/* Liquid level wave */}
                <path
                  d="M 665 240 Q 685 235 710 240 T 755 240"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="2"
                />
                <text x="710" y="260" fill="#e2e8f0" fontSize="10" textAnchor="middle">
                  {sepTemp} °C • {sepLevel}%
                </text>

                <rect x="665" y="285" width="90" height="22" rx="4" fill={t.badgeBg} />
                <text x="710" y="300" fill={t.badgeText} fontSize="10" fontWeight="bold" textAnchor="middle">
                  SHAP: {t.pct.toFixed(1)}%
                </text>
              </g>
            );
          })()}

          {/* ============================================================== */}
          {/* UNIT 5: RECYCLE COMPRESSOR                                     */}
          {/* ============================================================== */}
          {(() => {
            const t = getUnitTheme('Recycle Compressor');
            return (
              <g
                className="cursor-pointer transition-all duration-300"
                onClick={() => onSelectUnit('Recycle Compressor')}
              >
                {/* Compressor trapezoid shape */}
                <polygon
                  points="445,365 545,380 545,420 445,435"
                  fill={t.fill}
                  stroke={t.stroke}
                  strokeWidth={t.isSelected ? 3 : 2}
                  className="hover:stroke-sky-400"
                />
                <text x="495" y="395" fill={t.text} fontSize="11" fontWeight="bold" textAnchor="middle">
                  Compressor
                </text>
                <text x="495" y="408" fill="#cbd5e1" fontSize="9" textAnchor="middle">
                  {compWork} kW
                </text>

                <rect x="455" y="418" width="80" height="16" rx="4" fill={t.badgeBg} />
                <text x="495" y="430" fill={t.badgeText} fontSize="9" fontWeight="bold" textAnchor="middle">
                  SHAP: {t.pct.toFixed(1)}%
                </text>
              </g>
            );
          })()}

          {/* ============================================================== */}
          {/* UNIT 6: PRODUCT STRIPPER                                       */}
          {/* ============================================================== */}
          {(() => {
            const t = getUnitTheme('Product Stripper');
            return (
              <g
                className="cursor-pointer transition-all duration-300"
                onClick={() => onSelectUnit('Product Stripper')}
              >
                <rect
                  x="815"
                  y="160"
                  width="105"
                  height="220"
                  rx="18"
                  fill={t.fill}
                  stroke={t.stroke}
                  strokeWidth={t.isSelected ? 3 : 2}
                  className="hover:stroke-sky-400"
                />
                {/* Trays */}
                <line x1="825" y1="210" x2="910" y2="210" stroke="#475569" strokeWidth="1.5" strokeDasharray="3 3" />
                <line x1="825" y1="240" x2="910" y2="240" stroke="#475569" strokeWidth="1.5" strokeDasharray="3 3" />
                <line x1="825" y1="270" x2="910" y2="270" stroke="#475569" strokeWidth="1.5" strokeDasharray="3 3" />
                <line x1="825" y1="300" x2="910" y2="300" stroke="#475569" strokeWidth="1.5" strokeDasharray="3 3" />

                <text x="867" y="190" fill={t.text} fontSize="12" fontWeight="bold" textAnchor="middle">
                  Stripper
                </text>
                <text x="867" y="203" fill="#64748b" fontSize="9" textAnchor="middle">
                  Unit 6 (Product G/H)
                </text>

                <text x="867" y="330" fill="#e2e8f0" fontSize="10" textAnchor="middle">
                  {strpTemp} °C • {strpLevel}%
                </text>

                <rect x="822" y="345" width="90" height="22" rx="4" fill={t.badgeBg} />
                <text x="867" y="360" fill={t.badgeText} fontSize="10" fontWeight="bold" textAnchor="middle">
                  SHAP: {t.pct.toFixed(1)}%
                </text>
              </g>
            );
          })()}

          {/* Product Output Arrow Label */}
          <text x="900" y="420" fill="#10b981" fontSize="10" fontWeight="bold">
            Product G/H
          </text>
        </svg>
      </div>
    </div>
  );
});

