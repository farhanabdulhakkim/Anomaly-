"""
services/mission_service.py
============================
Orchestrates the full pipeline for a mission:
  1. Parse uploaded telemetry via logparser
  2. Remap coordinates using the field's permanent grid origin
  3. Run anomaly detection
  4. Persist telemetry points and anomaly counts
  5. Compute analytics summary
"""

import uuid
import os
from typing import List, Optional

import pandas as pd
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, LineString
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mission import Mission
from app.models.telemetry import TelemetryPoint
from app.models.anomaly import Anomaly
from app.models.analytics import AnalyticsSummary
from app.models.grid_cell import GridCell
from app.repositories.repositories import MissionRepository, FieldRepository, AnalyticsRepository
from app.detection.detectors import DetectorFactory
from app.schemas.schemas import MissionCreate

METRES_PER_DEG_LAT = 110_540.0
METRES_PER_DEG_LON = 109_290.0


def _is_standard_gps(lat: pd.Series, lon: pd.Series) -> bool:
    return lat.between(-90, 90).all() and lon.between(-180, 180).all()


def _normalise_to_field(raw_lat: pd.Series, raw_lon: pd.Series,
                        base_lat: float = 11.3390, base_lon: float = 77.7195,
                        width_m: float = 200.0, height_m: float = 200.0):
    def scale(s): return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else pd.Series([0.0] * len(s), index=s.index)
    mapped_lat = base_lat + scale(raw_lon) * height_m / METRES_PER_DEG_LAT
    mapped_lon = base_lon + scale(raw_lat) * width_m  / METRES_PER_DEG_LON
    return mapped_lat, mapped_lon


class MissionService:
    def __init__(self, db: AsyncSession):
        self.mission_repo = MissionRepository(db)
        self.field_repo   = FieldRepository(db)
        self.analytics_repo = AnalyticsRepository(db)

    async def create_mission(self, field_id: uuid.UUID, data: MissionCreate) -> Mission:
        mission = Mission(
            field_id=field_id,
            name=data.name,
            drone_model=data.drone_model,
            flight_altitude_m=data.flight_altitude_m,
            anomaly_mode=data.anomaly_mode,
            flight_date=data.flight_date,
            waypoints=data.waypoints,
            status="pending",
        )
        return await self.mission_repo.create(mission)

    async def process_telemetry(self, mission_id: uuid.UUID, telemetry_path: str) -> Mission:
        mission = await self.mission_repo.get_by_id(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        field = await self.field_repo.get_by_id(mission.field_id)
        grid_cells = await self.field_repo.get_grid_cells(mission.field_id)
        cell_lookup = {(c.row, c.col): c for c in grid_cells}

        mission.status = "processing"
        await self.mission_repo.update(mission)

        try:
            # 1. Parse telemetry using logparser
            df = self._load_telemetry(telemetry_path, field)

            # 2. Assign grid indices using the field's permanent origin
            df = self._assign_grid_indices(df, field)

            # 3. Run anomaly detection
            detector = DetectorFactory.get(mission.anomaly_mode)
            df = detector.detect(df)
            summary = detector.aggregate(df)

            # 4. Build flight path LINESTRING
            coords = list(zip(df["lon"], df["lat"]))
            flight_path = from_shape(LineString(coords), srid=4326) if len(coords) >= 2 else None

            # 5. Persist telemetry points
            telemetry_rows = self._build_telemetry_rows(df, mission_id)
            self.mission_repo.db.add_all(telemetry_rows)

            # 6. Persist anomaly counts per grid cell
            anomaly_rows = self._build_anomaly_rows(summary, mission_id, cell_lookup)
            await self.mission_repo.bulk_insert_anomalies(anomaly_rows)

            # 7. Update mission stats
            n_anom_cells  = sum(1 for v in summary.values() if v["count"] > 0)
            n_anom_points = int(df["anomaly"].sum())
            mission.flight_path        = flight_path
            mission.total_points       = len(df)
            mission.anomaly_point_count = n_anom_points
            mission.anomaly_cell_count  = n_anom_cells
            mission.duration_s         = float(df["elapsed_s"].max())
            mission.status             = "completed"
            await self.mission_repo.update(mission)

            # 8. Compute analytics
            await self._compute_analytics(mission, summary)

        except Exception as e:
            mission.status = "failed"
            await self.mission_repo.update(mission)
            raise

        return mission

    def _load_telemetry(self, path: str, field) -> pd.DataFrame:
        """Load telemetry from CSV or XLS file."""
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        df.columns = [c.strip().lower() for c in df.columns]
        df = df.rename(columns={"latitude": "raw_lat", "longitude": "raw_lon"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        if not _is_standard_gps(df["raw_lat"], df["raw_lon"]):
            df["lat"], df["lon"] = _normalise_to_field(df["raw_lat"], df["raw_lon"])
        else:
            df["lat"] = df["raw_lat"]
            df["lon"] = df["raw_lon"]

        t0 = df["timestamp"].iloc[0]
        df["elapsed_s"] = (df["timestamp"] - t0).dt.total_seconds()
        return df

    def _assign_grid_indices(self, df: pd.DataFrame, field) -> pd.DataFrame:
        """Use the field's permanent origin — never recompute from flight data."""
        df = df.copy()
        cell_m = field.cell_size_m
        north_m = (df["lat"] - field.origin_lat) * METRES_PER_DEG_LAT
        east_m  = (df["lon"] - field.origin_lon) * METRES_PER_DEG_LON
        df["grid_row"] = (north_m / cell_m).clip(lower=0).astype(int)
        df["grid_col"] = (east_m  / cell_m).clip(lower=0).astype(int)
        return df

    def _build_telemetry_rows(self, df: pd.DataFrame, mission_id: uuid.UUID) -> List[TelemetryPoint]:
        rows = []
        for _, r in df.iterrows():
            rows.append(TelemetryPoint(
                mission_id=mission_id,
                geom=from_shape(Point(float(r["lon"]), float(r["lat"])), srid=4326),
                altitude_m=float(r["altitude"]),
                speed_ms=float(r.get("speed", 0)),
                roll_deg=float(r["roll_deg"]) if "roll_deg" in r else None,
                pitch_deg=float(r["pitch_deg"]) if "pitch_deg" in r else None,
                yaw_deg=float(r["yaw_deg"]) if "yaw_deg" in r else None,
                elapsed_s=float(r["elapsed_s"]),
                grid_row=int(r["grid_row"]),
                grid_col=int(r["grid_col"]),
                is_anomaly=bool(r["anomaly"]),
                recorded_at=r["timestamp"],
            ))
        return rows

    def _build_anomaly_rows(self, summary: dict, mission_id: uuid.UUID,
                             cell_lookup: dict) -> List[Anomaly]:
        rows = []
        for (row, col), stats in summary.items():
            cell = cell_lookup.get((row, col))
            if cell is None:
                continue
            rows.append(Anomaly(
                mission_id=mission_id,
                grid_cell_id=cell.id,
                anomaly_count=stats["count"],
                total_points=stats["total"],
                density=stats["density"],
            ))
        return rows

    async def _compute_analytics(self, mission: Mission, summary: dict) -> None:
        anomaly_cells = [v for v in summary.values() if v["count"] > 0]
        total_cells   = len(summary)
        n_anom        = len(anomaly_cells)
        densities     = [v["density"] for v in anomaly_cells]

        prev = await self.mission_repo.get_previous_mission(mission.field_id, mission.id)
        reduction_pct = None
        cell_change   = None

        if prev:
            prev_analytics = await self.analytics_repo.get_by_mission(prev.id)
            if prev_analytics and prev_analytics.anomaly_cells > 0:
                reduction_pct = round(
                    (prev_analytics.anomaly_cells - n_anom) / prev_analytics.anomaly_cells * 100, 2
                )
                cell_change = n_anom - prev_analytics.anomaly_cells

        summary_row = AnalyticsSummary(
            mission_id=mission.id,
            total_cells=total_cells,
            anomaly_cells=n_anom,
            clean_cells=total_cells - n_anom,
            total_anomaly_points=mission.anomaly_point_count,
            avg_anomaly_density=round(sum(densities) / len(densities), 4) if densities else 0.0,
            max_anomaly_density=round(max(densities), 4) if densities else 0.0,
            prev_mission_id=prev.id if prev else None,
            anomaly_reduction_pct=reduction_pct,
            cell_change_count=cell_change,
        )
        await self.analytics_repo.upsert(summary_row)

    async def compare_missions(self, mission_a_id: uuid.UUID, mission_b_id: uuid.UUID) -> dict:
        a_anomalies = await self.mission_repo.get_anomalies(mission_a_id)
        b_anomalies = await self.mission_repo.get_anomalies(mission_b_id)

        a_cells = {str(a.grid_cell_id) for a in a_anomalies if a.anomaly_count > 0}
        b_cells = {str(b.grid_cell_id) for b in b_anomalies if b.anomaly_count > 0}

        a_count = len(a_cells)
        b_count = len(b_cells)
        reduction = round((a_count - b_count) / a_count * 100, 2) if a_count > 0 else 0.0

        return {
            "mission_a_id": mission_a_id,
            "mission_b_id": mission_b_id,
            "mission_a_anomaly_cells": a_count,
            "mission_b_anomaly_cells": b_count,
            "reduction_pct": reduction,
            "new_anomaly_cells": list(b_cells - a_cells),
            "resolved_anomaly_cells": list(a_cells - b_cells),
            "recurring_anomaly_cells": list(a_cells & b_cells),
        }

    async def get_anomaly_geojson(self, mission_id: uuid.UUID) -> dict:
        anomalies = await self.mission_repo.get_anomalies(mission_id)
        features = []
        for a in anomalies:
            c = a.grid_cell
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[c.sw_lon, c.sw_lat], [c.ne_lon, c.sw_lat],
                                     [c.ne_lon, c.ne_lat], [c.sw_lon, c.ne_lat],
                                     [c.sw_lon, c.sw_lat]]],
                },
                "properties": {
                    "row": c.row, "col": c.col,
                    "anomaly_count": a.anomaly_count,
                    "density": a.density,
                },
            })
        return {"type": "FeatureCollection", "features": features}
