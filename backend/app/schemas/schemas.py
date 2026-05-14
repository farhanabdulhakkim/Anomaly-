import uuid
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Field ─────────────────────────────────────────────────────────────────────

class FieldCreate(BaseModel):
    name: str
    rice_type: Optional[str] = None
    soil_type: Optional[str] = None
    irrigation_type: Optional[str] = None
    area_hectares: Optional[float] = None
    planting_date: Optional[date] = None
    cell_size_m: int = 10
    # GeoJSON polygon coordinates: [[[lon,lat], ...]]
    boundary_geojson: dict

class FieldUpdate(BaseModel):
    name: Optional[str] = None
    rice_type: Optional[str] = None
    soil_type: Optional[str] = None
    irrigation_type: Optional[str] = None
    area_hectares: Optional[float] = None
    planting_date: Optional[date] = None

class FieldOut(BaseModel):
    id: uuid.UUID
    name: str
    rice_type: Optional[str]
    soil_type: Optional[str]
    irrigation_type: Optional[str]
    area_hectares: Optional[float]
    planting_date: Optional[date]
    cell_size_m: int
    n_rows: Optional[int]
    n_cols: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Mission ───────────────────────────────────────────────────────────────────

class MissionCreate(BaseModel):
    name: str
    drone_model: Optional[str] = None
    flight_altitude_m: Optional[float] = None
    anomaly_mode: str = "rule_based"
    flight_date: Optional[datetime] = None
    waypoints: Optional[list] = None

class MissionOut(BaseModel):
    id: uuid.UUID
    field_id: uuid.UUID
    name: str
    drone_model: Optional[str]
    flight_altitude_m: Optional[float]
    anomaly_mode: str
    status: str
    version: int
    total_points: int
    anomaly_point_count: int
    anomaly_cell_count: int
    duration_s: Optional[float]
    flight_date: Optional[datetime]
    waypoint_filename: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Grid Cell ─────────────────────────────────────────────────────────────────

class GridCellOut(BaseModel):
    id: uuid.UUID
    row: int
    col: int
    centre_lat: float
    centre_lon: float
    sw_lat: float
    sw_lon: float
    ne_lat: float
    ne_lon: float
    model_config = {"from_attributes": True}


# ── Anomaly ───────────────────────────────────────────────────────────────────

class AnomalyOut(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    grid_cell_id: uuid.UUID
    anomaly_count: int
    total_points: int
    density: float
    model_config = {"from_attributes": True}


# ── Analytics ─────────────────────────────────────────────────────────────────

class AnalyticsOut(BaseModel):
    mission_id: uuid.UUID
    total_cells: int
    anomaly_cells: int
    clean_cells: int
    total_anomaly_points: int
    avg_anomaly_density: float
    max_anomaly_density: float
    anomaly_reduction_pct: Optional[float]
    cell_change_count: Optional[int]
    hotspot_cell_ids: Optional[list]
    computed_at: datetime
    model_config = {"from_attributes": True}


class MissionCompareOut(BaseModel):
    mission_a_id: uuid.UUID
    mission_b_id: uuid.UUID
    mission_a_anomaly_cells: int
    mission_b_anomaly_cells: int
    reduction_pct: float
    new_anomaly_cells: List[str]
    resolved_anomaly_cells: List[str]
    recurring_anomaly_cells: List[str]
