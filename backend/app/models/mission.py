import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, Text, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.db.session import Base


class MissionStatus(str):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


class AnomalyMode(str):
    random     = "random"
    rule_based = "rule_based"
    model      = "model"


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    drone_model: Mapped[str] = mapped_column(String(100), nullable=True)
    flight_altitude_m: Mapped[float] = mapped_column(Float, nullable=True)
    anomaly_mode: Mapped[str] = mapped_column(String(20), default="rule_based", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # PostGIS LINESTRING — drone flight path
    flight_path: Mapped[Geometry] = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)

    # Aggregated stats (denormalised for fast dashboard queries)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_point_count: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_cell_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float] = mapped_column(Float, nullable=True)

    # Waypoints / mission plan stored as JSON array
    waypoints: Mapped[dict] = mapped_column(JSON, nullable=True)
    waypoint_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    waypoint_raw: Mapped[str] = mapped_column(Text, nullable=True)

    flight_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    field: Mapped["Field"] = relationship("Field", back_populates="missions")
    telemetry_points: Mapped[list["TelemetryPoint"]] = relationship("TelemetryPoint", back_populates="mission", cascade="all, delete-orphan")
    anomalies: Mapped[list["Anomaly"]] = relationship("Anomaly", back_populates="mission", cascade="all, delete-orphan")
    analytics: Mapped[list["AnalyticsSummary"]] = relationship("AnalyticsSummary", back_populates="mission", foreign_keys="AnalyticsSummary.mission_id", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_missions_flight_path_gist", "flight_path", postgresql_using="gist"),
        Index("ix_missions_field_id", "field_id"),
    )
