/**
 * Complete TEP P&ID Topology & 52-Variable Mapping (Ground Truth).
 */

export interface PidUnitInfo {
  name: string;
  measuredSensors: string[];
  valves: string[];
  description: string;
}

export const PID_UNITS: Record<string, PidUnitInfo> = {
  'Feed & Purge System': {
    name: 'Feed & Purge System',
    description: 'A, D, E feeds, mixed A/C feed, purge gas composition analyzer',
    measuredSensors: [
      'A Feed Flow', 'D Feed Flow', 'E Feed Flow', 'A and C Feed Flow',
      'Purge Rate', 'Purge A Composition', 'Purge B Composition', 'Purge C Composition',
      'Purge D Composition', 'Purge E Composition', 'Purge F Composition',
      'Purge G Composition', 'Purge H Composition'
    ],
    valves: [
      'D Feed Valve', 'E Feed Valve', 'A Feed Valve', 'A and C Feed Valve', 'Purge Valve'
    ],
  },
  'Reactor': {
    name: 'Reactor',
    description: 'Exothermic gas-phase chemical reactor with internal cooling jacket',
    measuredSensors: [
      'Reactor Feed Rate', 'Reactor Pressure', 'Reactor Level', 'Reactor Temperature',
      'Reactor Cooling Water Outlet Temp', 'Feed A Composition', 'Feed B Composition',
      'Feed C Composition', 'Feed D Composition', 'Feed E Composition', 'Feed F Composition'
    ],
    valves: [
      'Reactor Cooling Water Flow Valve'
    ],
  },
  'Product Condenser': {
    name: 'Product Condenser',
    description: 'Horizontal shell-and-tube partial condenser cooling reactor effluent',
    measuredSensors: [
      'Condenser Cooling Water Outlet Temp'
    ],
    valves: [
      'Condenser Cooling Water Flow Valve'
    ],
  },
  'Vapor-Liquid Separator': {
    name: 'Vapor-Liquid Separator',
    description: 'Flash separation of liquid bottoms and overhead recycle/purge vapor',
    measuredSensors: [
      'Separator Temperature', 'Separator Level', 'Separator Pressure', 'Separator Underflow'
    ],
    valves: [
      'Separator Liquid Flow Valve'
    ],
  },
  'Recycle Compressor': {
    name: 'Recycle Compressor',
    description: 'Centrifugal gas compressor looping overhead vapor back to reactor',
    measuredSensors: [
      'Recycle Flow', 'Compressor Work'
    ],
    valves: [
      'Compressor Recycle Valve'
    ],
  },
  'Product Stripper': {
    name: 'Product Stripper',
    description: 'Stripping column removing volatile reactants from product stream',
    measuredSensors: [
      'Stripper Level', 'Stripper Pressure', 'Stripper Underflow', 'Stripper Temperature',
      'Stripper Steam Flow', 'Product D Composition', 'Product E Composition',
      'Product F Composition', 'Product G Composition', 'Product H Composition'
    ],
    valves: [
      'Stripper Product Flow Valve', 'Stripper Steam Flow Valve'
    ],
  },
};

export const SENSOR_DETAILS: Record<string, { tag: string; unit: string; min: number; max: number }> = {
  'A Feed Flow': { tag: 'xmeas_1', unit: 'kscmh', min: 0, max: 0.5 },
  'D Feed Flow': { tag: 'xmeas_2', unit: 'kg/hr', min: 2000, max: 5000 },
  'E Feed Flow': { tag: 'xmeas_3', unit: 'kg/hr', min: 2000, max: 6000 },
  'A and C Feed Flow': { tag: 'xmeas_4', unit: 'kscmh', min: 5, max: 15 },
  'Recycle Flow': { tag: 'xmeas_5', unit: 'kscmh', min: 20, max: 40 },
  'Reactor Feed Rate': { tag: 'xmeas_6', unit: 'kscmh', min: 30, max: 60 },
  'Reactor Pressure': { tag: 'xmeas_7', unit: 'kPa gauge', min: 2600, max: 2900 },
  'Reactor Level': { tag: 'xmeas_8', unit: '%', min: 40, max: 90 },
  'Reactor Temperature': { tag: 'xmeas_9', unit: '°C', min: 110, max: 140 },
  'Purge Rate': { tag: 'xmeas_10', unit: 'kscmh', min: 0.1, max: 1.0 },
  'Separator Temperature': { tag: 'xmeas_11', unit: '°C', min: 70, max: 100 },
  'Separator Level': { tag: 'xmeas_12', unit: '%', min: 30, max: 70 },
  'Separator Pressure': { tag: 'xmeas_13', unit: 'kPa gauge', min: 2500, max: 2800 },
  'Separator Underflow': { tag: 'xmeas_14', unit: 'm3/hr', min: 10, max: 40 },
  'Stripper Level': { tag: 'xmeas_15', unit: '%', min: 30, max: 70 },
  'Stripper Pressure': { tag: 'xmeas_16', unit: 'kPa gauge', min: 2900, max: 3300 },
  'Stripper Underflow': { tag: 'xmeas_17', unit: 'm3/hr', min: 10, max: 35 },
  'Stripper Temperature': { tag: 'xmeas_18', unit: '°C', min: 60, max: 80 },
  'Stripper Steam Flow': { tag: 'xmeas_19', unit: 'kg/hr', min: 800, max: 1500 },
  'Compressor Work': { tag: 'xmeas_20', unit: 'kW', min: 280, max: 400 },
  'Reactor Cooling Water Outlet Temp': { tag: 'xmeas_21', unit: '°C', min: 70, max: 110 },
  'Condenser Cooling Water Outlet Temp': { tag: 'xmeas_22', unit: '°C', min: 60, max: 90 },
  'D Feed Valve': { tag: 'xmv_1', unit: '% open', min: 0, max: 100 },
  'E Feed Valve': { tag: 'xmv_2', unit: '% open', min: 0, max: 100 },
  'A Feed Valve': { tag: 'xmv_3', unit: '% open', min: 0, max: 100 },
  'A and C Feed Valve': { tag: 'xmv_4', unit: '% open', min: 0, max: 100 },
  'Compressor Recycle Valve': { tag: 'xmv_5', unit: '% open', min: 0, max: 100 },
  'Purge Valve': { tag: 'xmv_6', unit: '% open', min: 0, max: 100 },
  'Separator Liquid Flow Valve': { tag: 'xmv_7', unit: '% open', min: 0, max: 100 },
  'Stripper Product Flow Valve': { tag: 'xmv_8', unit: '% open', min: 0, max: 100 },
  'Stripper Steam Flow Valve': { tag: 'xmv_9', unit: '% open', min: 0, max: 100 },
  'Reactor Cooling Water Flow Valve': { tag: 'xmv_10', unit: '% open', min: 0, max: 100 },
  'Condenser Cooling Water Flow Valve': { tag: 'xmv_11', unit: '% open', min: 0, max: 100 },
};

export const TEP_FAULTS: Record<number, string> = {
  0: 'Normal Operation (No Disturbance)',
  1: 'A/C Feed Ratio Step Disturbance (B Composition Constant)',
  2: 'B Composition Step Disturbance (A/C Ratio Constant)',
  3: 'D Feed Temperature Step Disturbance',
  4: 'Reactor Cooling Water Inlet Temp Step Disturbance',
  5: 'Condenser Cooling Water Inlet Temp Step Disturbance',
  6: 'A Feed Loss (Complete Loss of Reactant A)',
  7: 'C Header Pressure Loss (Step Reduction in Supply Pressure)',
  8: 'A, B, C Feed Composition Random Variation',
  9: 'D Feed Temperature Random Variation',
  10: 'C Feed Temperature Random Variation',
  11: 'Reactor Cooling Water Inlet Temp Random Variation',
  12: 'Condenser Cooling Water Inlet Temp Random Variation',
  13: 'Reaction Kinetics Drift (Catalyst Deactivation)',
  14: 'Reactor Cooling Water Valve Sticking',
  15: 'Condenser Cooling Water Valve Sticking',
  16: 'Unknown Disturbance 16',
  17: 'Unknown Disturbance 17',
  18: 'Unknown Disturbance 18',
  19: 'Unknown Disturbance 19',
  20: 'Unknown Disturbance 20',
  21: 'Stream 4 Valve Fixed Position (Manipulated Variable Failure)',
};
