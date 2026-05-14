import uuid
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.services.mission_service import MissionService
from app.repositories.repositories import MissionRepository, AnalyticsRepository
from app.schemas.schemas import MissionCreate, MissionOut, MissionCompareOut, AnalyticsOut

router = APIRouter(prefix="/api/fields/{field_id}/missions", tags=["missions"])


@router.post("", response_model=MissionOut, status_code=201)
async def create_mission(
    field_id: uuid.UUID,
    data: MissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = MissionService(db)
    return await svc.create_mission(field_id, data)


@router.get("", response_model=list[MissionOut])
async def list_missions(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = MissionRepository(db)
    return await repo.list_by_field(field_id)


@router.get("/{mission_id}", response_model=MissionOut)
async def get_mission(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = MissionRepository(db)
    mission = await repo.get_by_id(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.post("/{mission_id}/upload-telemetry", response_model=MissionOut)
async def upload_telemetry(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    file: UploadFile = File(...),
    flight_date: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload drone log file (XLS/CSV) and run the full anomaly detection pipeline."""
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Update flight date if provided
    if flight_date:
        repo = MissionRepository(db)
        mission = await repo.get_by_id(mission_id)
        if mission:
            mission.flight_date = datetime.fromisoformat(flight_date)
            await repo.update(mission)

    svc = MissionService(db)
    try:
        mission = await svc.process_telemetry(mission_id, tmp_path)
    finally:
        os.unlink(tmp_path)
    return mission


@router.post("/{mission_id}/upload-plan", response_model=MissionOut)
async def upload_mission_plan(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload Mission Planner autopilot plan (.waypoints / .plan / .txt).
    Stores the raw file content and parses waypoints as JSON.
    """
    repo = MissionRepository(db)
    mission = await repo.get_by_id(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    content = (await file.read()).decode("utf-8", errors="ignore")
    mission.waypoint_filename = file.filename
    mission.waypoint_raw = content

    # Parse waypoints — supports Mission Planner .waypoints format
    waypoints = []
    for line in content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("QGC") or line.startswith("#"):
            continue
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) >= 12:
            try:
                waypoints.append({
                    "seq":     int(parts[0]),
                    "frame":   int(parts[2]),
                    "command": int(parts[3]),
                    "lat":     float(parts[8]),
                    "lon":     float(parts[9]),
                    "alt":     float(parts[10]),
                })
            except (ValueError, IndexError):
                continue

    mission.waypoints = waypoints if waypoints else json.loads(content) if content.strip().startswith("{") else None
    await repo.update(mission)
    return mission


@router.get("/{mission_id}/plan")
async def get_mission_plan(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the stored autopilot plan for a mission."""
    repo = MissionRepository(db)
    mission = await repo.get_by_id(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return {
        "mission_id": mission_id,
        "waypoint_filename": mission.waypoint_filename,
        "waypoints": mission.waypoints,
        "waypoint_raw": mission.waypoint_raw,
    }


@router.get("/{mission_id}/flight-path")
async def get_flight_path(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the drone flight path as a GeoJSON LineString."""
    from sqlalchemy import select, text
    from app.models.mission import Mission as MissionModel
    repo = MissionRepository(db)
    mission = await repo.get_by_id(mission_id)
    if not mission or mission.flight_path is None:
        return {"type": "LineString", "coordinates": []}
    # Convert PostGIS geometry to GeoJSON using ST_AsGeoJSON
    result = await db.execute(
        text("SELECT ST_AsGeoJSON(flight_path) FROM missions WHERE id = :id"),
        {"id": str(mission_id)}
    )
    row = result.fetchone()
    if row and row[0]:
        return json.loads(row[0])
    return {"type": "LineString", "coordinates": []}


@router.get("/{mission_id}/analytics", response_model=AnalyticsOut)
async def get_analytics(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = AnalyticsRepository(db)
    analytics = await repo.get_by_mission(mission_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Analytics not yet computed")
    return analytics


@router.get("/{mission_id}/anomalies/geojson")
async def get_anomaly_geojson(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = MissionService(db)
    return await svc.get_anomaly_geojson(mission_id)


@router.get("/compare/{mission_a_id}/{mission_b_id}", response_model=MissionCompareOut)
async def compare_missions(
    field_id: uuid.UUID,
    mission_a_id: uuid.UUID,
    mission_b_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = MissionService(db)
    return await svc.compare_missions(mission_a_id, mission_b_id)
