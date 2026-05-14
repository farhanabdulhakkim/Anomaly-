import uuid
from datetime import datetime
from sqlalchemy import Float, Integer, ForeignKey, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AnalyticsSummary(Base):
    __tablename__ = "analytics_summary"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, unique=True)

    total_cells: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_cells: Mapped[int] = mapped_column(Integer, default=0)
    clean_cells: Mapped[int] = mapped_column(Integer, default=0)
    total_anomaly_points: Mapped[int] = mapped_column(Integer, default=0)
    avg_anomaly_density: Mapped[float] = mapped_column(Float, default=0.0)
    max_anomaly_density: Mapped[float] = mapped_column(Float, default=0.0)

    # Comparison with previous mission (null for first mission)
    prev_mission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id", ondelete="SET NULL"), nullable=True)
    anomaly_reduction_pct: Mapped[float] = mapped_column(Float, nullable=True)
    cell_change_count: Mapped[int] = mapped_column(Integer, nullable=True)

    # Top recurring hotspot cell ids as JSON list
    hotspot_cell_ids: Mapped[dict] = mapped_column(JSON, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mission: Mapped["Mission"] = relationship("Mission", back_populates="analytics", foreign_keys=[mission_id])
