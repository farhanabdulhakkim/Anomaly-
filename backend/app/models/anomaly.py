import uuid
from datetime import datetime
from sqlalchemy import Float, Integer, ForeignKey, DateTime, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Anomaly(Base):
    """
    Per-mission anomaly count for each grid cell.
    Joining with GridCell gives the spatial geometry for GIS queries.
    """
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    grid_cell_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grid_cells.id", ondelete="CASCADE"), nullable=False)

    anomaly_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    density: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mission: Mapped["Mission"] = relationship("Mission", back_populates="anomalies")
    grid_cell: Mapped["GridCell"] = relationship("GridCell", back_populates="anomalies")

    __table_args__ = (
        UniqueConstraint("mission_id", "grid_cell_id", name="uq_anomaly_mission_cell"),
        Index("ix_anomalies_mission_id", "mission_id"),
        Index("ix_anomalies_grid_cell_id", "grid_cell_id"),
    )
