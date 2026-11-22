"""
Configuration, Constants & Ground Truth Topology for Tennessee Eastman Process (TEP).
Defines standard 52 variables, physical P&ID unit mappings, fault definitions, and alarm limits.
"""
from typing import Dict, List, Tuple

# 52 TEP process variables (Downs & Vogel, 1993)
TEP_MEASURED_SENSORS: List[str] = [f"xmeas_{i}" for i in range(1, 42)]
TEP_MANIPULATED_VALVES: List[str] = [f"xmv_{i}" for i in range(1, 12)]
TEP_SENSORS: List[str] = TEP_MEASURED_SENSORS + TEP_MANIPULATED_VALVES

TEP_SENSOR_NAMES: List[str] = [
    # XMEAS 1-22 : flows, pressures, levels and temperatures
    "A Feed Flow", "D Feed Flow", "E Feed Flow", "A and C Feed Flow",
    "Recycle Flow", "Reactor Feed Rate", "Reactor Pressure", "Reactor Level",
    "Reactor Temperature", "Purge Rate", "Separator Temperature", "Separator Level",
    "Separator Pressure", "Separator Underflow", "Stripper Level", "Stripper Pressure",
    "Stripper Underflow", "Stripper Temperature", "Stripper Steam Flow", "Compressor Work",
    "Reactor Cooling Water Outlet Temp", "Condenser Cooling Water Outlet Temp",
    # XMEAS 23-41 : stream composition analysis
    "Feed A Composition", "Feed B Composition", "Feed C Composition", "Feed D Composition",
    "Feed E Composition", "Feed F Composition",
    "Purge A Composition", "Purge B Composition", "Purge C Composition", "Purge D Composition",
    "Purge E Composition", "Purge F Composition", "Purge G Composition", "Purge H Composition",
    "Product D Composition", "Product E Composition", "Product F Composition",
    "Product G Composition", "Product H Composition",
    # XMV 1-11 : manipulated (valve) variables
    "D Feed Valve", "E Feed Valve", "A Feed Valve", "A and C Feed Valve",
    "Compressor Recycle Valve", "Purge Valve", "Separator Liquid Flow Valve",
    "Stripper Liquid Product Valve", "Stripper Steam Valve",
    "Reactor Cooling Water Flow Valve", "Condenser Cooling Water Flow Valve",
]

SENSOR_LABELS: Dict[str, str] = dict(zip(TEP_SENSORS, TEP_SENSOR_NAMES))
REVERSE_SENSOR_LABELS: Dict[str, str] = {v: k for k, v in SENSOR_LABELS.items()}

# Ground Truth Chemical Engineering P&ID Unit Mappings
PID_UNITS: Dict[str, Dict[str, List[str]]] = {
    "Feed & Purge System": {
        "sensors": ["xmeas_1", "xmeas_2", "xmeas_3", "xmeas_4", "xmeas_10"] + [f"xmeas_{i}" for i in range(29, 37)],
        "valves": ["xmv_1", "xmv_2", "xmv_3", "xmv_4", "xmv_6"],
        "description": "Feed lines A, D, E, A/C mix and off-gas purge system."
    },
    "Reactor": {
        "sensors": ["xmeas_6", "xmeas_7", "xmeas_8", "xmeas_9", "xmeas_21"] + [f"xmeas_{i}" for i in range(23, 29)],
        "valves": ["xmv_10"],
        "description": "Continuous stirred-tank reactor (CSTR) with exothermic cooling jacket."
    },
    "Product Condenser": {
        "sensors": ["xmeas_22"],
        "valves": ["xmv_11"],
        "description": "Exothermic vapor-stream condenser with cooling water control."
    },
    "Vapor-Liquid Separator": {
        "sensors": ["xmeas_11", "xmeas_12", "xmeas_13", "xmeas_14"],
        "valves": ["xmv_7"],
        "description": "Phase flash separator splitting condensed liquid from recycle vapor."
    },
    "Recycle Compressor": {
        "sensors": ["xmeas_5", "xmeas_20"],
        "valves": ["xmv_5"],
        "description": "Centrifugal recycle compressor returning vapor to reactor feed."
    },
    "Product Stripper": {
        "sensors": ["xmeas_15", "xmeas_16", "xmeas_17", "xmeas_18", "xmeas_19"] + [f"xmeas_{i}" for i in range(37, 42)],
        "valves": ["xmv_8", "xmv_9"],
        "description": "Steam-heated stripping column separating product from volatile reactants."
    },
}

# Reverse mapping: sensor_id or readable_name -> unit_name
SENSOR_TO_UNIT: Dict[str, str] = {}
for unit_name, unit_data in PID_UNITS.items():
    for var in unit_data["sensors"] + unit_data["valves"]:
        SENSOR_TO_UNIT[var] = unit_name
        label = SENSOR_LABELS.get(var)
        if label:
            SENSOR_TO_UNIT[label] = unit_name

# Standard Downs & Vogel (1993) 21 Fault Disturbance Catalogue
TEP_FAULT_DEFINITIONS: Dict[int, Dict[str, str]] = {
    0: {"name": "Normal Operation", "type": "Steady State", "low_snr": False},
    1: {"name": "A/C feed ratio step change", "type": "Step", "low_snr": False},
    2: {"name": "B composition step change", "type": "Step", "low_snr": False},
    3: {"name": "D feed temperature step change", "type": "Step", "low_snr": True},
    4: {"name": "Reactor cooling water inlet temp step", "type": "Step", "low_snr": False},
    5: {"name": "Condenser cooling water inlet temp step", "type": "Step", "low_snr": False},
    6: {"name": "A feed loss (step)", "type": "Step", "low_snr": False},
    7: {"name": "C header pressure loss (step)", "type": "Step", "low_snr": False},
    8: {"name": "A, B, C feed composition random variation", "type": "Random Variation", "low_snr": False},
    9: {"name": "D feed temp random variation", "type": "Random Variation", "low_snr": True},
    10: {"name": "C feed temp random variation", "type": "Random Variation", "low_snr": False},
    11: {"name": "Reactor cooling water temp random variation", "type": "Random Variation", "low_snr": False},
    12: {"name": "Condenser cooling water temp random variation", "type": "Random Variation", "low_snr": False},
    13: {"name": "Reaction kinetics slow drift", "type": "Drift", "low_snr": False},
    14: {"name": "Reactor cooling water valve sticking", "type": "Stiction", "low_snr": False},
    15: {"name": "Condenser cooling water valve sticking", "type": "Stiction", "low_snr": True},
    16: {"name": "Heat exchanger fouling (unknown)", "type": "Drift", "low_snr": False},
    17: {"name": "Internal pressure fluctuation (unknown)", "type": "Unknown", "low_snr": False},
    18: {"name": "Inventory imbalance (unknown)", "type": "Unknown", "low_snr": False},
    19: {"name": "Condenser tube scaling (unknown)", "type": "Drift", "low_snr": False},
    20: {"name": "Purge valve stiction (unknown)", "type": "Stiction", "low_snr": False},
    21: {"name": "Stream 4 valve position fixed", "type": "Constant", "low_snr": False},
}

LOW_SNR_FAULTS = [3, 9, 15]

# Process flow connections (directional topological graph for P&ID rendering)
PROCESS_FLOW_CONNECTIONS: List[Tuple[str, str, str]] = [
    ("Feed & Purge System", "Reactor", "Raw Material Feed Line"),
    ("Reactor", "Product Condenser", "Reactor Vapor Effluent"),
    ("Product Condenser", "Vapor-Liquid Separator", "Condensed Slurry Line"),
    ("Vapor-Liquid Separator", "Product Stripper", "Liquid Bottoms Stream"),
    ("Vapor-Liquid Separator", "Recycle Compressor", "Overhead Vapor Recycle"),
    ("Recycle Compressor", "Reactor", "Recycle Feed Return"),
    ("Vapor-Liquid Separator", "Feed & Purge System", "Off-Gas Purge Header"),
]

# ISA-18.2 Alarm & Hysteresis Standards
WARN_ENTER: float = 0.70
WARN_CLEAR: float = 0.62
CRIT_ENTER: float = 0.85
CRIT_CLEAR: float = 0.77

ALARM_FLOOD_LIMIT: int = 10     # Max alarms allowed per 10-minute sliding window
SAMPLE_INTERVAL_MIN: float = 3.0 # TEP benchmark sample interval (3 minutes)
TTC_TREND_WINDOW: int = 15      # Trailing samples used to compute Time-To-Critical slope
