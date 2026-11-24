"""
Historian & Persistence Layer for TEP Predictive Maintenance.
Supports PostgreSQL / TimescaleDB via DATABASE_URL with automatic SQLite WAL mode fallback.
"""
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./tep_historian.db")

# Setup engine with appropriate parameters
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

# Enable WAL mode and normal synchronous writing for SQLite for high concurrent throughput
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[int] = mapped_column(Integer, index=True)
    model_mode: Mapped[str] = mapped_column(String(32), default="stacked_ensemble")
    risk_score: Mapped[float] = mapped_column(Float)
    health_index: Mapped[float] = mapped_column(Float)
    regime: Mapped[str] = mapped_column(String(16), index=True)
    top_fault_id: Mapped[int] = mapped_column(Integer)
    top_fault_conf: Mapped[float] = mapped_column(Float)
    sensor_health_score: Mapped[float] = mapped_column(Float)


class Alarm(Base):
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16)) # WARNING, CRITICAL
    fault_diagnosis: Mapped[str] = mapped_column(String(128))
    top_unit: Mapped[str] = mapped_column(String(64))
    top_shap_drivers_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True) # ACTIVE, ACKNOWLEDGED, RESOLVED, FALSE_ALARM
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    operator_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[str] = mapped_column(Text)
    user: Mapped[str] = mapped_column(String(64), default="ControlRoomOperator")


def init_db():
    """Create all tables in database if they don't already exist and seed demo records if empty."""
    Base.metadata.create_all(bind=engine)
    
    # Pre-seed realistic industrial alarms if table is empty for presentation demos
    session = SessionLocal()
    try:
        if session.query(Alarm).count() == 0:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            sample_drivers = [
                {"feature": "Reactor Cooling Water Flow Valve_m30", "display_name": "Cooling Water Valve", "shap_value": 0.42, "unit": "Reactor", "direction": "Pushes Risk UP"},
                {"feature": "Reactor Pressure_m30", "display_name": "Reactor Pressure", "shap_value": 0.38, "unit": "Reactor", "direction": "Pushes Risk UP"},
                {"feature": "Separator Temperature_m30", "display_name": "Separator Temp", "shap_value": 0.25, "unit": "Vapor-Liquid Separator", "direction": "Pushes Risk UP"}
            ]
            demo_alarms = [
                Alarm(
                    timestamp=now - timedelta(minutes=42),
                    run_id="DEMO_HISTORICAL",
                    step=180,
                    severity="CRITICAL",
                    fault_diagnosis="Fault 4: Reactor Cooling Water Inlet Temp Step",
                    top_unit="Reactor",
                    top_shap_drivers_json=json.dumps(sample_drivers),
                    status="RESOLVED",
                    acknowledged_by="Karthikeyan S",
                    operator_note="Cooling water supply loop inspected; bypass trim valve reset to nominal.",
                    updated_at=now - timedelta(minutes=25)
                ),
                Alarm(
                    timestamp=now - timedelta(minutes=28),
                    run_id="DEMO_HISTORICAL",
                    step=174,
                    severity="WARNING",
                    fault_diagnosis="Fault 1: A/C Feed Ratio Step Disturbance",
                    top_unit="Feed & Purge System",
                    top_shap_drivers_json=json.dumps(sample_drivers[:2]),
                    status="ACKNOWLEDGED",
                    acknowledged_by="Lokesh T A",
                    operator_note="Feed stream A analyzer drift noted; ratio trim adjusted by -1.8%.",
                    updated_at=now - timedelta(minutes=15)
                ),
                Alarm(
                    timestamp=now - timedelta(minutes=12),
                    run_id="DEMO_HISTORICAL",
                    step=168,
                    severity="WARNING",
                    fault_diagnosis="Fault 6: A Feed Loss (Stream 1)",
                    top_unit="Feed & Purge System",
                    top_shap_drivers_json=json.dumps(sample_drivers[:2]),
                    status="RESOLVED",
                    acknowledged_by="ShiftSupervisor",
                    operator_note="Feed pump A restarted; line pressure stabilized.",
                    updated_at=now - timedelta(minutes=5)
                )
            ]
            session.add_all(demo_alarms)
            
            # Initial audit logs
            demo_logs = [
                AuditLog(
                    timestamp=now - timedelta(minutes=40),
                    action="ACKNOWLEDGE_ALARM",
                    details=json.dumps({"alarm_id": 1, "severity": "CRITICAL", "unit": "Reactor"}),
                    user="Karthikeyan S"
                ),
                AuditLog(
                    timestamp=now - timedelta(minutes=25),
                    action="RESOLVE_ALARM",
                    details=json.dumps({"alarm_id": 1, "status": "RESOLVED", "note": "Bypass reset"}),
                    user="Karthikeyan S"
                ),
                AuditLog(
                    timestamp=now - timedelta(minutes=15),
                    action="OPERATOR_SETPOINT_TRIM",
                    details=json.dumps({"valve": "XMV_10", "offset": "-1.8%"}),
                    user="Lokesh T A"
                )
            ]
            session.add_all(demo_logs)
            session.commit()
    except Exception as e:
        session.rollback()
        print(f"[init_db] Seed note: {e}")
    finally:
        session.close()


def get_db():
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
