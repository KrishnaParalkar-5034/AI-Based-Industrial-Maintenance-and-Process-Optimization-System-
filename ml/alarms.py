"""
ISA-18.2 Industrial Alarm Hysteresis & Flood Detection Engine.
Prevents alarm chattering using dual-threshold deadbands and monitors operator alarm rate.
"""
from collections import deque
from typing import Any, Dict, List, Optional

import numpy as np

from .config import (
    ALARM_FLOOD_LIMIT,
    CRIT_CLEAR,
    CRIT_ENTER,
    SAMPLE_INTERVAL_MIN,
    WARN_CLEAR,
    WARN_ENTER,
)


class ISA18AlarmManager:
    """
    Stateful Alarm State Machine following ANSI/ISA-18.2 Management of Alarm Systems.
    Maintains hysteresis deadbands and a rolling alarm counter.
    """
    def __init__(
        self,
        warn_enter: float = WARN_ENTER,
        warn_clear: float = WARN_CLEAR,
        crit_enter: float = CRIT_ENTER,
        crit_clear: float = CRIT_CLEAR,
        flood_limit: int = ALARM_FLOOD_LIMIT,
        flood_window_minutes: float = 10.0
    ):
        self.warn_enter = warn_enter
        self.warn_clear = warn_clear
        self.crit_enter = crit_enter
        self.crit_clear = crit_clear
        self.flood_limit = flood_limit
        self.flood_window_minutes = flood_window_minutes

        self.current_regime: str = "NORMAL"
        self.alarm_timestamps: deque = deque() # Timestamps in minutes
        self.total_alarms_count: int = 0
        self.active_alarm_id: Optional[int] = None

    def evaluate_step(self, risk: float, step: int, sample_min: float = SAMPLE_INTERVAL_MIN) -> Dict[str, Any]:
        """
        Evaluate single time step:
          - Applies stateful hysteresis transitions.
          - Detects new alarm transition events.
          - Updates 10-minute rolling alarm flood monitor.
        """
        old_regime = self.current_regime
        new_regime = old_regime
        current_time_min = step * sample_min

        # Stateful Hysteresis Transition Logic
        if old_regime == "NORMAL":
            if risk >= self.crit_enter:
                new_regime = "CRITICAL"
            elif risk >= self.warn_enter:
                new_regime = "WARNING"
        elif old_regime == "WARNING":
            if risk >= self.crit_enter:
                new_regime = "CRITICAL"
            elif risk < self.warn_clear: # Must drop BELOW warn_clear to return to NORMAL
                new_regime = "NORMAL"
        elif old_regime == "CRITICAL":
            if risk < self.crit_clear: # Must drop BELOW crit_clear
                if risk < self.warn_clear:
                    new_regime = "NORMAL"
                else:
                    new_regime = "WARNING"

        # Check if an alarm was newly raised or escalated
        new_alarm_raised = False
        if new_regime in ["WARNING", "CRITICAL"] and old_regime == "NORMAL":
            new_alarm_raised = True
        elif new_regime == "CRITICAL" and old_regime == "WARNING":
            new_alarm_raised = True

        if new_alarm_raised:
            self.alarm_timestamps.append(current_time_min)
            self.total_alarms_count += 1

        # Purge timestamps older than rolling flood window
        cutoff = current_time_min - self.flood_window_minutes
        while self.alarm_timestamps and self.alarm_timestamps[0] < cutoff:
            self.alarm_timestamps.popleft()

        alarms_in_window = len(self.alarm_timestamps)
        is_flood = alarms_in_window >= self.flood_limit

        self.current_regime = new_regime

        return {
            "regime": new_regime,
            "previous_regime": old_regime,
            "transition": new_regime != old_regime,
            "new_alarm_raised": new_alarm_raised,
            "alarms_in_10min": alarms_in_window,
            "alarm_flood": is_flood,
            "hysteresis_bounds": {
                "warn_enter": self.warn_enter,
                "warn_clear": self.warn_clear,
                "crit_enter": self.crit_enter,
                "crit_clear": self.crit_clear,
            }
        }

    def reset(self):
        self.current_regime = "NORMAL"
        self.alarm_timestamps.clear()
        self.total_alarms_count = 0
