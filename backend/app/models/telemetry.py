import uuid
from datetime import datetime
from sqlalchemy import Float, DateTime, ForeignKey, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.db.session import Base


class TelemetryPoint(Base):
    __tablename__ = "telemetry_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)

    # PostGIS POINT — WGS-84
    geom: Mapped[Geometry] = mapped_column(Geometry("POINT", srid=4326), nullable=False)

    # Raw values
    altitude_m: Mapped[float] = mapped_column(Float, nullable=True)
    speed_ms: Mapped[float] = mapped_column(Float, nullable=True)
    roll_deg: Mapped[float] = mapped_column(Float, nullable=True)
    pitch_deg: Mapped[float] = mapped_column(Float, nullable=True)
    yaw_deg: Mapped[float] = mapped_column(Float, nullable=True)
    elapsed_s: Mapped[float] = mapped_column(Float, nullable=True)

    # Grid assignment
    grid_row: Mapped[int] = mapped_column(Integer, nullable=True)
    grid_col: Mapped[int] = mapped_column(Integer, nullable=True)

    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    mission: Mapped["Mission"] = relationship("Mission", back_populates="telemetry_points")

    __table_args__ = (
        Index("ix_telemetry_geom_gist", "geom", postgresql_using="gist"),
        Index("ix_telemetry_mission_id", "mission_id"),
    )
