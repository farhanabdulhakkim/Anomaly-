"""
services/field_service.py
=========================
Handles field creation and PERMANENT grid generation.

Grid immutability guarantee:
  Once a field's grid is generated (origin_lat, origin_lon, cell_size_m,
  n_rows, n_cols), it is NEVER regenerated. All future missions for this
  field use the same GridCell rows from the database.
"""

import uuid
import json
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon, Point, mapping

from app.models.field import Field
from app.models.grid_cell import GridCell
from app.repositories.repositories import FieldRepository
from app.schemas.schemas import FieldCreate, FieldUpdate

METRES_PER_DEG_LAT = 110_540.0
METRES_PER_DEG_LON = 109_290.0


class FieldService:
    def __init__(self, db: AsyncSession):
        self.repo = FieldRepository(db)

    async def create_field(self, owner_id: uuid.UUID, data: FieldCreate) -> Field:
        # Convert GeoJSON boundary to PostGIS geometry
        coords = data.boundary_geojson["coordinates"][0]
        shapely_poly = Polygon(coords)  # coords are [lon, lat] pairs
        boundary_geom = from_shape(shapely_poly, srid=4326)

        # Derive SW origin from boundary envelope
        bounds = shapely_poly.bounds  # (minx, miny, maxx, maxy) = (min_lon, min_lat, ...)
        origin_lat = bounds[1] - (data.cell_size_m / METRES_PER_DEG_LAT) / 2
        origin_lon = bounds[0] - (data.cell_size_m / METRES_PER_DEG_LON) / 2

        width_m  = (bounds[2] - bounds[0]) * METRES_PER_DEG_LON
        height_m = (bounds[3] - bounds[1]) * METRES_PER_DEG_LAT
        n_cols = max(1, int(width_m  / data.cell_size_m) + 1)
        n_rows = max(1, int(height_m / data.cell_size_m) + 1)

        field = Field(
            owner_id=owner_id,
            name=data.name,
            rice_type=data.rice_type,
            soil_type=data.soil_type,
            irrigation_type=data.irrigation_type,
            area_hectares=data.area_hectares,
            planting_date=data.planting_date,
            cell_size_m=data.cell_size_m,
            boundary=boundary_geom,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            n_rows=n_rows,
            n_cols=n_cols,
        )
        field = await self.repo.create(field)

        # Generate permanent grid cells
        cells = self._generate_grid_cells(field)
        await self.repo.bulk_insert_grid_cells(cells)

        return field

    def _generate_grid_cells(self, field: Field) -> List[GridCell]:
        cells = []
        cell_m = field.cell_size_m
        for row in range(field.n_rows):
            for col in range(field.n_cols):
                sw_lat = field.origin_lat + row * cell_m / METRES_PER_DEG_LAT
                sw_lon = field.origin_lon + col * cell_m / METRES_PER_DEG_LON
                ne_lat = sw_lat + cell_m / METRES_PER_DEG_LAT
                ne_lon = sw_lon + cell_m / METRES_PER_DEG_LON

                poly = Polygon([
                    (sw_lon, sw_lat), (ne_lon, sw_lat),
                    (ne_lon, ne_lat), (sw_lon, ne_lat),
                    (sw_lon, sw_lat),
                ])
                cells.append(GridCell(
                    field_id=field.id,
                    row=row, col=col,
                    geom=from_shape(poly, srid=4326),
                    centre_lat=(sw_lat + ne_lat) / 2,
                    centre_lon=(sw_lon + ne_lon) / 2,
                    sw_lat=sw_lat, sw_lon=sw_lon,
                    ne_lat=ne_lat, ne_lon=ne_lon,
                ))
        return cells

    async def get_field(self, field_id: uuid.UUID) -> Field:
        field = await self.repo.get_by_id(field_id)
        if not field:
            raise ValueError(f"Field {field_id} not found")
        return field

    async def list_fields(self, owner_id: uuid.UUID) -> List[Field]:
        return await self.repo.list_by_owner(owner_id)

    async def update_field(self, field_id: uuid.UUID, data: FieldUpdate) -> Field:
        field = await self.get_field(field_id)
        for key, val in data.model_dump(exclude_none=True).items():
            setattr(field, key, val)
        return await self.repo.update(field)

    async def get_grid_geojson(self, field_id: uuid.UUID) -> dict:
        cells = await self.repo.get_grid_cells(field_id)
        features = []
        for c in cells:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[c.sw_lon, c.sw_lat], [c.ne_lon, c.sw_lat],
                                     [c.ne_lon, c.ne_lat], [c.sw_lon, c.ne_lat],
                                     [c.sw_lon, c.sw_lat]]],
                },
                "properties": {"id": str(c.id), "row": c.row, "col": c.col,
                                "centre_lat": c.centre_lat, "centre_lon": c.centre_lon},
            })
        return {"type": "FeatureCollection", "features": features}
