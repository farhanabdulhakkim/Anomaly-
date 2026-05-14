import uuid
from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, Integer, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.db.session import Base


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rice_type: Mapped[str] = mapped_column(String(100), nullable=True)
    soil_type: Mapped[str] = mapped_column(String(100), nullable=True)
    irrigation_type: Mapped[str] = mapped_column(String(100), nullable=True)
    area_hectares: Mapped[float] = mapped_column(Float, nullable=True)
    planting_date: Mapped[date] = mapped_column(Date, nullable=True)
    cell_size_m: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # PostGIS POLYGON — WGS-84 (SRID 4326)
    boundary: Mapped[Geometry] = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)

    # Derived from boundary — stored for fast access
    origin_lat: Mapped[float] = mapped_column(Float, nullable=True)
    origin_lon: Mapped[float] = mapped_column(Float, nullable=True)
    n_rows: Mapped[int] = mapped_column(Integer, nullable=True)
    n_cols: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="fields")
    grid_cells: Mapped[list["GridCell"]] = relationship("GridCell", back_populates="field", cascade="all, delete-orphan")
    missions: Mapped[list["Mission"]] = relationship("Mission", back_populates="field", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_fields_boundary_gist", "boundary", postgresql_using="gist"),
    )
