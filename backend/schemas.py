"""
Pydantic v2 Schemas for TEP Predictive Maintenance Backend API.
Strict type validation for REST requests, responses, and real-time WebSocket frames.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class StreamControlRequest(BaseModel):
    action: str = Field(..., description="Action: play, pause, seek, speed, switch_run, toggle_mode, inject_fault, update_hysteresis, switch_adapter")
    speed: Optional[float] = Field(None, ge=0.2, le=10.0, description="Playback speed multiplier")
    step: Optional[int] = Field(None, ge=0, description="Target sample step for seek")
    run_id: Optional[str] = Field(None, description="Simulation run identifier to switch to")
    model_mode: Optional[str] = Field(None, description="Active scoring mode: stacked_ensemble, xgboost, lstm_fcn, anomaly")
    adapter_type: Optional[str] = Field(None, description="Target adapter: replay or live_sim")
    fault_id: Optional[int] = Field(None, ge=0, le=21, description="Fault ID to inject")
    warn_enter: Optional[float] = Field(None, ge=0.1, le=0.9)
    warn_clear: Optional[float] = Field(None, ge=0.1, le=0.9)
    crit_enter: Optional[float] = Field(None, ge=0.2, le=1.0)
    crit_clear: Optional[float] = Field(None, ge=0.2, le=1.0)
    operator_user: Optional[str] = Field("ControlRoomOperator")


class StreamStatusResponse(BaseModel):
    is_playing: bool
    speed: float
    current_run_id: str
    current_step: int
    total_steps: int
    active_model_mode: str
    available_runs: List[str]
    hysteresis_thresholds: Dict[str, float]
    adapter_type: Optional[str] = "replay"
    active_fault_id: Optional[int] = 0


class AlarmUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status: ACKNOWLEDGED, RESOLVED, FALSE_ALARM")
    acknowledged_by: Optional[str] = Field("Operator-1")
    operator_note: Optional[str] = Field(None, description="Operational notes or RCA tags")


class AlarmResponse(BaseModel):
    id: int
    timestamp: datetime
    run_id: str
    step: int
    severity: str
    fault_diagnosis: str
    top_unit: str
    top_shap_drivers: Optional[List[Dict[str, Any]]] = None
    status: str
    acknowledged_by: Optional[str] = None
    operator_note: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    action: str
    details: Dict[str, Any]
    user: str

    model_config = {"from_attributes": True}


class TelemetryFrame(BaseModel):
    run_id: str
    step: int
    total_steps: int
    timestamp: str
    model_mode: str
    readings: Dict[str, float]
    deviations_sigma: Dict[str, float]
    channel_flags: Dict[str, List[str]]
    sensor_health_score: float
    risk_score: float
    health_index: float
    regime: str
    alarm_flood: bool
    alarms_in_10min: int
    unit_attributions_pct: Dict[str, float]
    top_fault_id: int
    top_fault_name: str
    top_fault_conf: float
    top_3_faults: List[Dict[str, Any]]
    ttc: Dict[str, Any]
    pillar_scores: Dict[str, float]
    fault_onset_sample: Optional[int] = None


class ExplainabilityResponse(BaseModel):
    run_id: str
    step: int
    base_value: float
    top_drivers: List[Dict[str, Any]]
    unit_attributions_raw: Dict[str, float]
    unit_attributions_pct: Dict[str, float]
    primary_contributing_unit: str
    prescriptive_actions: Dict[str, Any]


class CSVAnalysisResponse(BaseModel):
    total_rows: int
    peak_risk: float
    mean_risk: float
    overall_regime: str
    alarms_triggered: int
    top_diagnosed_fault_id: int
    top_diagnosed_fault_name: str
    top_fault_confidence: float
    primary_contributing_unit: str
    time_series: List[Dict[str, Any]]
    summary_markdown: str


class SystemInfoResponse(BaseModel):
    model_artifacts: Dict[str, Any]
    database: Dict[str, Any]
    runtime: Dict[str, Any]

