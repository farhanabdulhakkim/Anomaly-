import uuid
from sqlalchemy import Integer, Float, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.db.session import Base


class GridCell(Base):
    """
    Permanent grid cells generated once per field.
    Grid(row=10, col=5) for field X is immutable across all missions.
    Anomaly counts are stored per-mission in the Anomaly table.
    """
    __tablename__ = "grid_cells"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)

    row: Mapped[int] = mapped_column(Integer, nullable=False)
    col: Mapped[int] = mapped_column(Integer, nullable=False)

    # PostGIS POLYGON for the cell boundary — WGS-84
    geom: Mapped[Geometry] = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)

    centre_lat: Mapped[float] = mapped_column(Float, nullable=False)
    centre_lon: Mapped[float] = mapped_column(Float, nullable=False)
    sw_lat: Mapped[float] = mapped_column(Float, nullable=False)
    sw_lon: Mapped[float] = mapped_column(Float, nullable=False)
    ne_lat: Mapped[float] = mapped_column(Float, nullable=False)
    ne_lon: Mapped[float] = mapped_column(Float, nullable=False)

    field: Mapped["Field"] = relationship("Field", back_populates="grid_cells")
    anomalies: Mapped[list["Anomaly"]] = relationship("Anomaly", back_populates="grid_cell")

    __table_args__ = (
        UniqueConstraint("field_id", "row", "col", name="uq_grid_cell_field_row_col"),
        Index("ix_grid_cells_geom_gist", "geom", postgresql_using="gist"),
        Index("ix_grid_cells_field_id", "field_id"),
    )
