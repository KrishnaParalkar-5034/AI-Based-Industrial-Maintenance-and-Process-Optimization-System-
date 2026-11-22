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
    """Create all tables in database if they don't already exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
