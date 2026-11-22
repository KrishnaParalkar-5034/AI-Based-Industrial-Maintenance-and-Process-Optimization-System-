"""
FastAPI Decoupled Application for TEP Predictive Maintenance & Process Optimization.
Exposes real-time WebSocket telemetry, REST endpoints, TreeSHAP explainability,
ISA-18.2 alarm management, shift-handover reporting, and Prometheus /metrics.
"""
import asyncio
import csv
from datetime import datetime, timezone
import io
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import pandas as pd
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ml.config import SENSOR_LABELS, SENSOR_TO_UNIT, TEP_FAULT_DEFINITIONS, TEP_SENSORS, REVERSE_SENSOR_LABELS
from ml.data_pipeline import compute_causal_features
from ml.explainability import compute_exact_shap_attributions, generate_prescriptive_actions

from .db import Alarm, AuditLog, TelemetryEvent, get_db, init_db
from .engine import engine_instance, MODELS_DIR
from .adapters import LiveSimulatorAdapter
from .schemas import (
    AlarmResponse,
    AlarmUpdateRequest,
    AuditLogResponse,
    CSVAnalysisResponse,
    ExplainabilityResponse,
    StreamControlRequest,
    StreamStatusResponse,
    SystemInfoResponse,
)

# Initialize database tables on startup
init_db()

app = FastAPI(
    title="AI-Based Industrial Maintenance & Process Optimization API",
    description="Decoupled backend service providing high-frequency process telemetry, 21-class fault diagnostics, and ISA-18.2 alarm management for Tennessee Eastman Process.",
    version="2.0.0"
)

# Enable CORS for React/Vite development and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Deployment Expiry Guardrail (72-hour auto-kill demo window)
APP_EXPIRES_AT_STR = os.environ.get("APP_EXPIRES_AT", "").strip()
APP_EXPIRES_AT: Optional[datetime] = None
if APP_EXPIRES_AT_STR:
    try:
        clean_str = APP_EXPIRES_AT_STR.replace("Z", "+00:00")
        APP_EXPIRES_AT = datetime.fromisoformat(clean_str)
        if APP_EXPIRES_AT.tzinfo is None:
            APP_EXPIRES_AT = APP_EXPIRES_AT.replace(tzinfo=timezone.utc)
        print(f"[SECURITY] APP_EXPIRES_AT active: {APP_EXPIRES_AT.isoformat()}")
    except Exception as e:
        print(f"[WARNING] Could not parse APP_EXPIRES_AT='{APP_EXPIRES_AT_STR}': {e}")


@app.middleware("http")
async def check_deployment_expiry_middleware(request, call_next):
    if APP_EXPIRES_AT is not None:
        path = request.url.path
        if path not in ("/health", "/health/"):
            now_utc = datetime.now(timezone.utc)
            if now_utc >= APP_EXPIRES_AT:
                return Response(
                    content=json.dumps({
                        "detail": "Deployment demo window expired",
                        "status": 503,
                        "expires_at": APP_EXPIRES_AT_STR,
                        "current_time_utc": now_utc.isoformat()
                    }),
                    status_code=503,
                    media_type="application/json"
                )
    return await call_next(request)

# Active WebSocket connections registry
active_connections: List[WebSocket] = []


# ==============================================================================
# HEALTH & PROMETHEUS METRICS
# ==============================================================================

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Check service health, database connection, model loading status, and deployment expiry window."""
    db_ok = False
    try:
        db.execute(func.now())
        db_ok = True
    except Exception:
        db_ok = False

    models_loaded = engine_instance.bundle is not None
    now_utc = datetime.now(timezone.utc)
    is_expired = (APP_EXPIRES_AT is not None) and (now_utc >= APP_EXPIRES_AT)
    status_str = "expired" if is_expired else ("healthy" if (db_ok and models_loaded) else "degraded")
    return {
        "status": status_str,
        "database_connected": db_ok,
        "models_loaded": models_loaded,
        "current_run": engine_instance.adapter.get_current_run_id() if engine_instance.adapter else None,
        "advisory_mode": True,
        "expires_at": APP_EXPIRES_AT_STR or None,
        "is_expired": is_expired,
        "timestamp": now_utc.isoformat()
    }


@app.get("/metrics")
def prometheus_metrics(db: Session = Depends(get_db)):
    """Expose Prometheus-formatted operational and model monitoring metrics."""
    active_alarms = db.query(Alarm).filter(Alarm.status == "ACTIVE").count()
    crit_alarms = db.query(Alarm).filter(Alarm.status == "ACTIVE", Alarm.severity == "CRITICAL").count()
    total_events = db.query(TelemetryEventCount := func.count(Alarm.id)).scalar() or 0

    lines = [
        "# HELP tep_active_ws_clients Number of connected telemetry WebSocket clients.",
        "# TYPE tep_active_ws_clients gauge",
        f"tep_active_ws_clients {len(active_connections)}",
        "# HELP tep_active_alarms_total Total active alarms in the system.",
        "# TYPE tep_active_alarms_total gauge",
        f"tep_active_alarms_total {active_alarms}",
        "# HELP tep_critical_alarms_total Total critical alarms active.",
        "# TYPE tep_critical_alarms_total gauge",
        f"tep_critical_alarms_total {crit_alarms}",
        "# HELP tep_playback_playing Current telemetry playback state.",
        "# TYPE tep_playback_playing gauge",
        f"tep_playback_playing {1 if engine_instance.is_playing else 0}",
        "# HELP tep_playback_speed Telemetry playback speed multiplier.",
        "# TYPE tep_playback_speed gauge",
        f"tep_playback_speed {engine_instance.playback_speed}",
        "# HELP tep_inference_latency_ms Real-time model inference and feature extraction latency in milliseconds.",
        "# TYPE tep_inference_latency_ms gauge",
        f"tep_inference_latency_ms {round(engine_instance.last_latency_ms, 2)}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


# ==============================================================================
# STREAM CONTROL & STATUS
# ==============================================================================

@app.get("/api/v1/stream/status", response_model=StreamStatusResponse)
def get_stream_status():
    """Retrieve current telemetry playback state, available runs, and thresholds."""
    if not engine_instance.adapter:
        raise HTTPException(status_code=503, detail="Telemetry adapter uninitialized.")

    is_sim = isinstance(engine_instance.adapter, LiveSimulatorAdapter)
    adapter_type = "simulator" if is_sim else "replay"
    active_fault_id = getattr(engine_instance.adapter, "active_fault", 0) if is_sim else 0

    return StreamStatusResponse(
        is_playing=engine_instance.is_playing,
        speed=engine_instance.playback_speed,
        current_run_id=engine_instance.adapter.get_current_run_id(),
        current_step=engine_instance.current_step,
        total_steps=engine_instance.adapter.get_total_steps(),
        active_model_mode=engine_instance.model_mode,
        available_runs=engine_instance.adapter.get_available_runs(),
        hysteresis_thresholds={
            "warn_enter": engine_instance.alarm_mgr.warn_enter,
            "warn_clear": engine_instance.alarm_mgr.warn_clear,
            "crit_enter": engine_instance.alarm_mgr.crit_enter,
            "crit_clear": engine_instance.alarm_mgr.crit_clear,
        },
        adapter_type=adapter_type,
        active_fault_id=active_fault_id
    )


@app.post("/api/v1/stream/control")
def control_stream(req: StreamControlRequest, db: Session = Depends(get_db)):
    """
    Control telemetry streaming: play, pause, seek, speed, switch_run, toggle_mode, inject_fault.
    All configuration changes are logged to the immutable audit trail.
    """
    action = req.action.lower()
    audit_details = {"action": action}

    if action == "play":
        total = engine_instance.adapter.get_total_steps()
        if engine_instance.current_step >= total - 1:
            engine_instance.current_step = 0
            engine_instance.alarm_mgr.reset()
            engine_instance.recent_risk_history.clear()
            audit_details["auto_rewound"] = True
        engine_instance.is_playing = True
    elif action == "pause":
        engine_instance.is_playing = False
    elif action == "seek" and req.step is not None:
        total = engine_instance.adapter.get_total_steps()
        engine_instance.current_step = max(0, min(req.step, total - 1))
        audit_details["seek_step"] = engine_instance.current_step
    elif action == "speed" and req.speed is not None:
        engine_instance.playback_speed = float(req.speed)
        audit_details["speed"] = req.speed
    elif action == "switch_run" and req.run_id is not None:
        success = engine_instance.adapter.set_active_run(req.run_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Run '{req.run_id}' not found.")
        engine_instance.current_step = 0
        engine_instance.alarm_mgr.reset()
        engine_instance.recent_risk_history.clear()
        audit_details["switched_to_run"] = req.run_id
    elif action == "toggle_mode" and req.model_mode is not None:
        valid_modes = ["stacked_ensemble", "xgboost", "lstm_fcn", "anomaly"]
        if req.model_mode not in valid_modes:
            raise HTTPException(status_code=400, detail=f"Mode must be one of {valid_modes}")
        engine_instance.model_mode = req.model_mode
        audit_details["model_mode"] = req.model_mode
    elif action == "inject_fault" and req.fault_id is not None:
        if not isinstance(engine_instance.adapter, LiveSimulatorAdapter):
            engine_instance.switch_adapter("simulator")
            audit_details["switched_to_simulator"] = True
        engine_instance.adapter.inject_fault(req.fault_id)
        if req.fault_id > 0:
            engine_instance.is_playing = True
        audit_details["injected_fault"] = req.fault_id
    elif action == "switch_adapter":
        target = req.adapter_type or "replay"
        mode_desc = engine_instance.switch_adapter(target)
        if target.lower() in ["simulator", "live", "live_sim"]:
            engine_instance.is_playing = True
        audit_details["switched_adapter"] = target
        audit_details["description"] = mode_desc
    elif action == "update_hysteresis":
        if req.warn_enter: engine_instance.alarm_mgr.warn_enter = req.warn_enter
        if req.warn_clear: engine_instance.alarm_mgr.warn_clear = req.warn_clear
        if req.crit_enter: engine_instance.alarm_mgr.crit_enter = req.crit_enter
        if req.crit_clear: engine_instance.alarm_mgr.crit_clear = req.crit_clear
        audit_details["thresholds"] = {
            "warn_enter": engine_instance.alarm_mgr.warn_enter,
            "warn_clear": engine_instance.alarm_mgr.warn_clear,
            "crit_enter": engine_instance.alarm_mgr.crit_enter,
            "crit_clear": engine_instance.alarm_mgr.crit_clear,
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown control action: {action}")

    # Log to audit trail
    log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        action=f"CONTROL_{action.upper()}",
        details=json.dumps(audit_details),
        user=req.operator_user or "ControlRoomOperator"
    )
    db.add(log)
    db.commit()

    return {"status": "success", "action": action, "details": audit_details}


# ==============================================================================
# WEBSOCKET REAL-TIME TELEMETRY STREAM
# ==============================================================================

@app.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """
    Sub-second real-time telemetry stream.
    Pushes comprehensive TelemetryFrame JSON payloads with 52 sensor values,
    deviations, signal quality, risk, ISA-18.2 regimes, and 21-class diagnostics.
    """
    if APP_EXPIRES_AT is not None and datetime.now(timezone.utc) >= APP_EXPIRES_AT:
        await websocket.accept()
        try:
            await websocket.send_json({"error": "Deployment demo window expired", "status": 503})
        except Exception:
            pass
        await websocket.close(code=1008, reason="Deployment demo window expired")
        return

    await websocket.accept()
    active_connections.append(websocket)
    print(f"[ws] Client connected. Total active clients: {len(active_connections)}")

    last_sent_key = None
    last_keepalive = 0.0

    try:
        while True:
            is_advance = False
            # Advance step if currently playing
            if engine_instance.is_playing and engine_instance.adapter:
                total = engine_instance.adapter.get_total_steps()
                if engine_instance.current_step < total - 1:
                    engine_instance.current_step += 1
                    is_advance = True
                else:
                    engine_instance.is_playing = False # Pause at end of run

            current_key = (
                engine_instance.adapter.get_current_run_id() if engine_instance.adapter else "",
                isinstance(engine_instance.adapter, LiveSimulatorAdapter),
                engine_instance.current_step,
                engine_instance.model_mode,
                engine_instance.alarm_mgr.warn_enter,
                engine_instance.alarm_mgr.warn_clear,
                engine_instance.alarm_mgr.crit_enter,
                engine_instance.alarm_mgr.crit_clear,
            )

            now = time.monotonic()
            state_changed = (current_key != last_sent_key)
            is_keepalive = (now - last_keepalive >= 5.0)

            if state_changed or is_keepalive:
                try:
                    frame_data = engine_instance.process_step(engine_instance.current_step, is_step_advance=is_advance)
                    await websocket.send_text(json.dumps(frame_data))
                    last_sent_key = current_key
                    last_keepalive = now
                except Exception as e:
                    print(f"[ws] Error processing step {engine_instance.current_step}: {e}")

            # Sleep interval: when playing, scaled by speed; when paused, lightweight sleep
            if engine_instance.is_playing:
                delay = max(0.1, 1.0 / max(0.1, engine_instance.playback_speed))
            else:
                delay = 0.2
            await asyncio.sleep(delay)

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"[ws] Client disconnected. Remaining: {len(active_connections)}")
    except Exception as exc:
        if websocket in active_connections:
            active_connections.remove(websocket)
        print(f"[ws] WebSocket error: {exc}")


# ==============================================================================
# EXPLAINABILITY (TreeSHAP) & ROOT CAUSE
# ==============================================================================

@app.get("/api/v1/explain/{run_id}/{step}", response_model=ExplainabilityResponse)
def get_explainability(run_id: str, step: int):
    """
    Return exact TreeSHAP waterfall feature contributions and unit attributions
    for specified run and sample step.
    """
    if not engine_instance.bundle:
        raise HTTPException(status_code=503, detail="Models uninitialized.")

    adapter = engine_instance.adapter
    # Temporarily fetch row
    curr_row, _, _ = adapter.get_step_data(step)
    feat_cols = engine_instance.bundle["features"]
    X_scaled = engine_instance.bundle["scaler"].transform(curr_row[feat_cols].values.reshape(1, -1).astype(float))

    shap_res = compute_exact_shap_attributions(engine_instance.bundle["xgb_binary"], feat_cols, X_scaled[0], top_k=10)

    # Multi-class diagnosis and calibrated risk regime for sample step
    cal_xgb = engine_instance.bundle.get("xgb_calibrated", engine_instance.bundle["xgb_binary"])
    risk_p = float(cal_xgb.predict_proba(X_scaled)[0, 1])
    step_regime = "CRITICAL" if risk_p >= 0.85 else ("WARNING" if risk_p >= 0.70 else "NORMAL")

    multi_probs = engine_instance.bundle["xgb_multi"].predict_proba(X_scaled)[0]
    if step_regime != "NORMAL":
        non_zero_probs = multi_probs[1:]
        top_fault = int(np.argmax(non_zero_probs)) + 1
    else:
        top_fault = 0

    prescriptive = generate_prescriptive_actions(
        top_fault,
        shap_res["primary_contributing_unit"],
        shap_res["top_drivers"],
        regime=step_regime
    )

    return ExplainabilityResponse(
        run_id=run_id,
        step=step,
        base_value=shap_res["base_value"],
        top_drivers=shap_res["top_drivers"],
        unit_attributions_raw=shap_res["unit_attributions_raw"],
        unit_attributions_pct=shap_res["unit_attributions_pct"],
        primary_contributing_unit=shap_res["primary_contributing_unit"],
        prescriptive_actions=prescriptive
    )


# ==============================================================================
# ALARMS & OPERATOR ACTIONS
# ==============================================================================

@app.get("/api/v1/alarms", response_model=List[AlarmResponse])
def get_alarms(
    status: Optional[str] = Query(None, description="ACTIVE, ACKNOWLEDGED, RESOLVED, FALSE_ALARM"),
    severity: Optional[str] = Query(None, description="WARNING, CRITICAL"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Query persistent alarms with optional status and severity filters."""
    query = db.query(Alarm)
    if status:
        query = query.filter(Alarm.status == status.upper())
    if severity:
        query = query.filter(Alarm.severity == severity.upper())

    records = query.order_by(desc(Alarm.id)).limit(limit).all()

    # Parse JSON drivers
    results = []
    for r in records:
        drivers = None
        try:
            drivers = json.loads(r.top_shap_drivers_json) if r.top_shap_drivers_json else None
        except Exception:
            pass
        results.append(AlarmResponse(
            id=r.id,
            timestamp=r.timestamp,
            run_id=r.run_id,
            step=r.step,
            severity=r.severity,
            fault_diagnosis=r.fault_diagnosis,
            top_unit=r.top_unit,
            top_shap_drivers=drivers,
            status=r.status,
            acknowledged_by=r.acknowledged_by,
            operator_note=r.operator_note,
            updated_at=r.updated_at
        ))
    return results


@app.patch("/api/v1/alarms/{alarm_id}", response_model=AlarmResponse)
def update_alarm(alarm_id: int, req: AlarmUpdateRequest, db: Session = Depends(get_db)):
    """Acknowledge, resolve, or tag an alarm with operator notes."""
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found.")

    old_status = alarm.status
    alarm.status = req.status.upper()
    if req.acknowledged_by:
        alarm.acknowledged_by = req.acknowledged_by
    if req.operator_note:
        alarm.operator_note = req.operator_note
    alarm.updated_at = datetime.now(timezone.utc)

    # Log to audit trail
    log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        action="UPDATE_ALARM_STATUS",
        details=json.dumps({
            "alarm_id": alarm_id,
            "old_status": old_status,
            "new_status": alarm.status,
            "operator": req.acknowledged_by,
            "note": req.operator_note
        }),
        user=req.acknowledged_by or "Operator"
    )
    db.add(log)
    db.commit()
    db.refresh(alarm)

    return AlarmResponse.model_validate(alarm)


# ==============================================================================
# BENCHMARK METRICS & SHIFT HANDOVER REPORTS
# ==============================================================================

@app.get("/api/v1/models/benchmarks")
def get_model_benchmarks():
    """Serve full metrics.json reporting pillar vs. ensemble benchmarks and lead-time audit."""
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            return json.load(f)
    return {"message": "Metrics not generated yet. Run python -m ml.train_colab."}


@app.get("/api/v1/reports/shift-handover")
def generate_shift_handover_report(format: str = Query("html", pattern="^(html|json)$"), db: Session = Depends(get_db)):
    """
    Generate downloadable, print-ready Shift Handover Report summarizing plant health KPIs,
    active and resolved alarms, operator notes, and system audit events.
    """
    total_alarms = db.query(Alarm).count()
    active_alarms = db.query(Alarm).filter(Alarm.status == "ACTIVE").all()
    resolved_alarms = db.query(Alarm).filter(Alarm.status.in_(["RESOLVED", "FALSE_ALARM"])).all()
    audit_events = db.query(AuditLog).order_by(desc(AuditLog.id)).limit(20).all()

    report_data = {
        "report_title": "Tennessee Eastman Plant - Shift Handover & Reliability Report",
        "generated_at": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M:%S UTC"),
        "advisory_notice": "Advisory Decision Support System - No automated physical actuation.",
        "active_alarms_count": len(active_alarms),
        "resolved_alarms_count": len(resolved_alarms),
        "active_alarms": [{"id": a.id, "severity": a.severity, "unit": a.top_unit, "fault": a.fault_diagnosis, "status": a.status} for a in active_alarms],
        "audit_logs": [{"id": l.id, "time": l.timestamp.strftime("%H:%M:%S"), "action": l.action, "user": l.user} for l in audit_events]
    }

    if format == "json":
        return report_data

    # Return clean, print-ready HTML report
    alarm_rows = "".join([
        f"<tr><td>#{a['id']}</td><td><span class='badge {a['severity']}'>{a['severity']}</span></td><td>{a['unit']}</td><td>{a['fault']}</td><td>{a['status']}</td></tr>"
        for a in report_data["active_alarms"]
    ]) or "<tr><td colspan='5' style='text-align:center;'>No Active Alarms at Shift Handover</td></tr>"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>TEP Shift Handover Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0b111e; color: #e2e8f0; margin: 40px; }}
        h1 {{ color: #3b82f6; font-size: 24px; border-bottom: 2px solid #1e293b; padding-bottom: 12px; }}
        .header {{ display: flex; justify-content: space-between; margin-bottom: 25px; }}
        .card {{ background: #131d2e; border: 1px solid #1e293b; border-radius: 8px; padding: 18px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th, td {{ border: 1px solid #1e293b; padding: 10px 14px; text-align: left; }}
        th {{ background: #1e293b; color: #94a3b8; font-weight: 600; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
        .WARNING {{ background: #b45309; color: #fef3c7; }}
        .CRITICAL {{ background: #b91c1c; color: #fee2e2; }}
        .btn {{ display: inline-block; background: #2563eb; color: #fff; padding: 8px 16px; border-radius: 6px; text-decoration: none; cursor: pointer; }}
        @media print {{ .no-print {{ display: none; }} body {{ background: #fff; color: #000; }} .card {{ border: 1px solid #ccc; background: #fff; }} th {{ background: #eee; color: #000; }} }}
    </style>
</head>
<body>
    <div class="no-print" style="text-align: right; margin-bottom: 15px;">
        <button class="btn" onclick="window.print()">Print / Export PDF</button>
    </div>
    <div class="header">
        <div>
            <h1>🏭 Tennessee Eastman Process Handover</h1>
            <p style="color: #64748b; font-size: 13px;">AI Predictive Maintenance Advisory Console</p>
        </div>
        <div style="text-align: right; color: #94a3b8; font-size: 13px;">
            <p><strong>Generated:</strong> {report_data['generated_at']}</p>
            <p style="color: #10b981;"><strong>Mode:</strong> Human-in-the-Loop Advisory</p>
        </div>
    </div>
    <div class="card">
        <h3>Shift Operational Health Summary</h3>
        <p>Active Unresolved Alarms: <strong>{report_data['active_alarms_count']}</strong> &nbsp;|&nbsp; Resolved / Addressed: <strong>{report_data['resolved_alarms_count']}</strong></p>
    </div>
    <div class="card">
        <h3>Active Alarms Pending Next Shift</h3>
        <table>
            <thead>
                <tr><th>ID</th><th>Severity</th><th>Primary Unit</th><th>Diagnosed Fault</th><th>Status</th></tr>
            </thead>
            <tbody>{alarm_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h3>Recent Operator Actions & Audit Trail</h3>
        <table>
            <thead><tr><th>Time</th><th>Action</th><th>User</th></tr></thead>
            <tbody>
                {''.join([f"<tr><td>{l['time']}</td><td>{l['action']}</td><td>{l['user']}</td></tr>" for l in report_data['audit_logs'][:10]])}
            </tbody>
        </table>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ==============================================================================
# BATCH CSV ANALYSIS & SAMPLE DATA
# ==============================================================================

@app.post("/api/v1/analyze/csv", response_model=CSVAnalysisResponse)
async def analyze_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Batch analyze uploaded CSV containing TEP variables.
    Computes rolling causal features, calibrated XGBoost & 21-class fault diagnosis,
    peak risk metrics, ISA-18.2 regimes, and TreeSHAP root-cause unit attribution.
    """
    if not engine_instance.bundle:
        raise HTTPException(status_code=503, detail="Model bundle not loaded.")

    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV file: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    # Column mapping: if columns have xmeas_ or xmv_, map to human readable names
    rename_map = {k: v for k, v in SENSOR_LABELS.items() if k in df.columns}
    if rename_map:
        df = df.rename(columns=rename_map)

    sensors = engine_instance.bundle["sensors"]
    normal_mean = engine_instance.bundle["normal_mean"]
    feat_cols = engine_instance.bundle["features"]
    scaler = engine_instance.bundle["scaler"]
    cal_xgb = engine_instance.bundle.get("xgb_calibrated", engine_instance.bundle["xgb_binary"])
    xgb_multi = engine_instance.bundle["xgb_multi"]

    # Fill any missing sensors with normal baseline mean
    for s in sensors:
        if s not in df.columns:
            df[s] = float(normal_mean.get(s, 50.0))

    if "run_id" not in df.columns:
        df["run_id"] = "BATCH_UPLOAD"
    if "sample" not in df.columns:
        df["sample"] = np.arange(len(df), dtype=np.int32)

    # Compute causal multi-scale rolling features
    try:
        feat_df = compute_causal_features(df, sensors)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature computation failed: {str(e)}")

    # Impute any missing feature columns with 0.0
    for col in feat_cols:
        if col not in feat_df.columns:
            feat_df[col] = 0.0

    X_scaled = scaler.transform(feat_df[feat_cols].values.astype(np.float32))

    # Binary calibrated risk & 21-class diagnosis
    probs_xgb = cal_xgb.predict_proba(X_scaled)[:, 1]
    multi_probs = xgb_multi.predict_proba(X_scaled)
    top_faults = np.argmax(multi_probs, axis=1)
    top_confs = np.max(multi_probs, axis=1)

    peak_risk = float(round(float(np.max(probs_xgb)), 4))
    mean_risk = float(round(float(np.mean(probs_xgb)), 4))
    alarms_count = int(np.sum(probs_xgb >= 0.70))

    if peak_risk >= 0.85:
        overall_regime = "CRITICAL"
    elif peak_risk >= 0.70:
        overall_regime = "WARNING"
    else:
        overall_regime = "NORMAL"

    # Identify dominant fault
    abnormal_mask = probs_xgb >= 0.50
    if np.any(abnormal_mask):
        dominant_fault_id = int(np.argmax(np.bincount(top_faults[abnormal_mask])))
        dominant_conf = float(round(float(np.mean(top_confs[abnormal_mask])), 3))
    else:
        dominant_fault_id = int(np.argmax(np.bincount(top_faults)))
        dominant_conf = float(round(float(np.mean(top_confs)), 3))

    dominant_fault_name = TEP_FAULT_DEFINITIONS.get(dominant_fault_id, {}).get("name", f"Fault {dominant_fault_id}")

    # TreeSHAP on peak risk row to find primary contributing unit
    peak_idx = int(np.argmax(probs_xgb))
    shap_res = compute_exact_shap_attributions(
        engine_instance.bundle["xgb_binary"],
        feat_cols,
        X_scaled[peak_idx],
        top_k=5
    )
    primary_unit = shap_res["primary_contributing_unit"]

    # Construct sample time series (limit to 300 points for smooth charting)
    step_stride = max(1, len(df) // 300)
    time_series = []
    for i in range(0, len(df), step_stride):
        r_score = float(round(float(probs_xgb[i]), 4))
        r_regime = "CRITICAL" if r_score >= 0.85 else ("WARNING" if r_score >= 0.70 else "NORMAL")
        time_series.append({
            "sample": int(df["sample"].iloc[i]),
            "risk_score": r_score,
            "regime": r_regime,
            "top_fault_id": int(top_faults[i]),
            "top_fault_name": TEP_FAULT_DEFINITIONS.get(int(top_faults[i]), {}).get("name", "Unknown"),
            "confidence": float(round(float(top_confs[i]), 3))
        })

    summary_md = (
        f"### Batch Process Telemetry Analysis Summary\n"
        f"- **Rows Analyzed:** {len(df)} samples\n"
        f"- **Peak Risk Score:** `{peak_risk:.4f}` ({overall_regime})\n"
        f"- **Mean Process Risk:** `{mean_risk:.4f}`\n"
        f"- **Warning/Critical Excursions:** `{alarms_count}` samples\n"
        f"- **Dominant Diagnosed Disturbance:** **Fault {dominant_fault_id}** — *{dominant_fault_name}* (Mean Confidence: `{dominant_conf * 100:.1f}%`)\n"
        f"- **Primary Contributing Unit:** **{primary_unit}**\n"
    )

    # Log action to audit trail
    log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        action="BATCH_CSV_ANALYSIS",
        details=json.dumps({
            "filename": file.filename,
            "rows": len(df),
            "peak_risk": peak_risk,
            "regime": overall_regime,
            "dominant_fault": dominant_fault_id
        }),
        user="ControlRoomOperator"
    )
    db.add(log)
    db.commit()

    return CSVAnalysisResponse(
        total_rows=len(df),
        peak_risk=peak_risk,
        mean_risk=mean_risk,
        overall_regime=overall_regime,
        alarms_triggered=alarms_count,
        top_diagnosed_fault_id=dominant_fault_id,
        top_diagnosed_fault_name=dominant_fault_name,
        top_fault_confidence=dominant_conf,
        primary_contributing_unit=primary_unit,
        time_series=time_series,
        summary_markdown=summary_md
    )


@app.get("/api/v1/analyze/sample-csv")
def download_sample_csv():
    """
    Generate and download a valid 60-row TEP CSV dataset with realistic normal and fault dynamics
    for immediate batch testing.
    """
    if engine_instance.bundle and "test" in engine_instance.bundle and not engine_instance.bundle["test"].empty:
        test_df = engine_instance.bundle["test"]
        f1_runs = test_df[test_df["run_id"].str.startswith("F01")]
        sample_df = f1_runs.iloc[:60].copy() if not f1_runs.empty else test_df.iloc[:60].copy()
    else:
        from ml.data_pipeline import generate_synthetic_tep_21
        sample_df = generate_synthetic_tep_21(runs_per_fault=1, n_samples=60, onset=30)

    # Keep only sample and sensor columns
    sensor_cols = [c for c in sample_df.columns if c in SENSOR_LABELS.values()]
    export_df = sample_df[["sample"] + sensor_cols] if "sample" in sample_df.columns else sample_df[sensor_cols]
    
    csv_str = export_df.to_csv(index=False)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tep_sample_batch.csv"}
    )


# ==============================================================================
# AUDIT LOGS & COMPLIANCE TRAIL
# ==============================================================================

@app.get("/api/v1/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Query system and operator audit logs with optional action/user filters."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if user:
        query = query.filter(AuditLog.user.ilike(f"%{user}%"))

    records = query.order_by(desc(AuditLog.id)).limit(limit).all()
    results = []
    for r in records:
        try:
            details = json.loads(r.details) if r.details else {}
        except Exception:
            details = {"raw": r.details}
        results.append(AuditLogResponse(
            id=r.id,
            timestamp=r.timestamp,
            action=r.action,
            details=details,
            user=r.user
        ))
    return results


@app.get("/api/v1/audit-logs/export")
def export_audit_logs_csv(db: Session = Depends(get_db)):
    """Export the immutable compliance audit trail as a downloadable CSV file."""
    records = db.query(AuditLog).order_by(desc(AuditLog.id)).limit(1000).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["ID", "Timestamp (UTC)", "Action", "Operator User", "Details"])
    for r in records:
        writer.writerow([r.id, r.timestamp.isoformat(), r.action, r.user, r.details])

    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tep_compliance_audit_trail.csv"}
    )


# ==============================================================================
# SYSTEM HEALTH & MODEL HOT-RELOAD
# ==============================================================================

@app.get("/api/v1/system/info", response_model=SystemInfoResponse)
def get_system_info(db: Session = Depends(get_db)):
    """Retrieve detailed system environment, model artifacts metadata, and database metrics."""
    bundle_stat = os.stat(engine_instance.bundle_path) if os.path.exists(engine_instance.bundle_path) else None
    lstm_stat = os.stat(engine_instance.lstm_path) if os.path.exists(engine_instance.lstm_path) else None
    ae_stat = os.stat(engine_instance.ae_path) if os.path.exists(engine_instance.ae_path) else None
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")
    metrics_stat = os.stat(metrics_path) if os.path.exists(metrics_path) else None

    # Count DB records
    total_events = db.query(func.count(Alarm.id)).scalar() or 0
    total_audits = db.query(func.count(AuditLog.id)).scalar() or 0

    return SystemInfoResponse(
        model_artifacts={
            "bundle": {
                "exists": bundle_stat is not None,
                "size_kb": round(bundle_stat.st_size / 1024, 1) if bundle_stat else 0,
                "modified": datetime.fromtimestamp(bundle_stat.st_mtime, timezone.utc).isoformat() if bundle_stat else None,
            },
            "lstm_fcn": {
                "exists": lstm_stat is not None,
                "size_kb": round(lstm_stat.st_size / 1024, 1) if lstm_stat else 0,
                "modified": datetime.fromtimestamp(lstm_stat.st_mtime, timezone.utc).isoformat() if lstm_stat else None,
            },
            "autoencoder": {
                "exists": ae_stat is not None,
                "size_kb": round(ae_stat.st_size / 1024, 1) if ae_stat else 0,
                "modified": datetime.fromtimestamp(ae_stat.st_mtime, timezone.utc).isoformat() if ae_stat else None,
            },
            "metrics": {
                "exists": metrics_stat is not None,
                "modified": datetime.fromtimestamp(metrics_stat.st_mtime, timezone.utc).isoformat() if metrics_stat else None,
            }
        },
        database={
            "engine": "PostgreSQL/TimescaleDB" if "postgresql" in os.environ.get("DATABASE_URL", "") else "SQLite WAL",
            "total_alarms": total_events,
            "total_audit_logs": total_audits,
            "status": "connected"
        },
        runtime={
            "python_version": os.sys.version.split()[0],
            "torch_version": getattr(__import__("torch"), "__version__", "N/A"),
            "xgboost_version": getattr(__import__("xgboost"), "__version__", "N/A"),
            "active_adapter": type(engine_instance.adapter).__name__ if engine_instance.adapter else "None",
            "active_run_id": engine_instance.adapter.get_current_run_id() if engine_instance.adapter else "None",
            "active_model_mode": engine_instance.model_mode,
            "dataset_origin": engine_instance.bundle.get("dataset_origin", "synthetic_ar1") if engine_instance.bundle else "unknown",
            "available_runs_count": len(engine_instance.adapter.get_available_runs()) if engine_instance.adapter else 0,
            "last_latency_ms": engine_instance.last_latency_ms,
            "active_ws_connections": len(active_connections)
        }
    )


@app.post("/api/v1/models/reload")
def reload_models(db: Session = Depends(get_db)):
    """Trigger dynamic hot-reloading of model weights and pipeline artifacts from disk."""
    res = engine_instance.reload_models()
    log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        action="HOT_RELOAD_MODELS",
        details=json.dumps(res),
        user="ControlRoomOperator"
    )
    db.add(log)
    db.commit()
    return res


@app.post("/api/v1/system/reset-db")
def reset_demo_database(db: Session = Depends(get_db)):
    """
    Clear historical alarms, telemetry events, and audit logs for clean live demos.
    Leaves schema and model artifacts intact.
    """
    db.query(Alarm).delete()
    db.query(TelemetryEvent).delete()
    db.query(AuditLog).delete()

    reset_log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        action="SYSTEM_RESET_DB",
        details=json.dumps({"status": "clean_reset", "reason": "operator_demo_reset"}),
        user="ControlRoomOperator"
    )
    db.add(reset_log)
    db.commit()

    # Reset engine in-memory state
    engine_instance.current_step = 0
    engine_instance.alarm_mgr.reset()
    engine_instance.recent_risk_history.clear()
    engine_instance.last_persisted_run_step = None

    return {"status": "success", "message": "Demo database successfully reset and historian cleared."}


# ==============================================================================
# STATIC FRONTEND SPA SERVING (Single-Container Production Mode)
# ==============================================================================

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_catchall(full_path: str):
    """
    Serve compiled React SPA assets with client-side routing fallback.
    Registered strictly AFTER all /api, /ws, /health, /metrics routes.
    """
    candidate = (FRONTEND_DIST / full_path).resolve()
    try:
        candidate.relative_to(FRONTEND_DIST.resolve())
        if full_path and candidate.is_file():
            return FileResponse(candidate)
    except ValueError:
        pass

    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    return HTMLResponse(
        "<html><head><title>TEP SCADA Platform</title></head>"
        "<body style='font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 40px;'>"
        "<h2>🏭 TEP SCADA Platform Service Online</h2>"
        "<p>FastAPI backend APIs and WebSocket streaming are fully operational.</p>"
        "<p><em>Note: Frontend SPA dist bundle not detected at this mount path.</em></p>"
        "</body></html>",
        status_code=200
    )
