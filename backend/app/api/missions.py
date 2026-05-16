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
from app.detection.cnn_pipeline import bounds_from_waypoints, run_video_cnn_detection

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


@router.post("/{mission_id}/upload-video", response_model=MissionOut)
async def upload_video(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    video: UploadFile = File(...),
    csv_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload drone video + ArduPilot CSV, run CNN pipeline, store Folium map."""
    from app.repositories.repositories import MissionRepository

    repo = MissionRepository(db)
    mission = await repo.get_by_id(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    # Save uploads to temp files
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
        vf.write(await video.read())
        video_path = vf.name

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as cf:
        cf.write(await csv_file.read())
        csv_path = cf.name

    backend_root = Path(__file__).resolve().parents[2]
    map_dir = backend_root / "maps"
    work_dir = map_dir / str(mission_id)
    map_dir.mkdir(parents=True, exist_ok=True)
    grid_path = map_dir / f"{mission_id}_grid.png"
    map_path = map_dir / f"{mission_id}_map.html"

    mission.status = "processing"
    await repo.update(mission)

    try:
        # Build Folium map inputs first so CMD waypoint bounds can guide the CNN grid.
        from final_log import parse_log, build_map
        pos_df, gps_df, last_mission_wps = parse_log(csv_path)

        cmd_waypoints = mission.waypoints
        if not cmd_waypoints and not last_mission_wps.empty:
            cmd_waypoints = [
                {"lat": float(wp.lat), "lon": float(wp.lng)}
                for _, wp in last_mission_wps.iterrows()
            ]

        result = run_video_cnn_detection(
            video_path=video_path,
            gps_log_path=csv_path,
            output_grid_path=grid_path,
            work_dir=work_dir,
            cmd_bounds=bounds_from_waypoints(cmd_waypoints),
        )
        anomalies = [
            {
                "lat": a.lat,
                "lng": a.lng,
                "severity": "medium",
                "detections": 1,
                "frame": a.frame_index,
                "confidence": a.confidence,
            }
            for a in result.anomalies
        ]

        build_map(pos_df, gps_df, last_mission_wps, anomalies, str(map_path))

        # Update mission stats
        mission.anomaly_point_count = len(anomalies)
        mission.anomaly_cell_count  = len(set((a["lat"], a["lng"]) for a in anomalies))
        mission.total_points = result.frames_processed
        mission.status = "completed"
        await repo.update(mission)

    except Exception as e:
        mission.status = "failed"
        await repo.update(mission)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(video_path)
        os.unlink(csv_path)

    return mission


@router.get("/{mission_id}/map-html", response_class=None)
async def get_map_html(
    field_id: uuid.UUID,
    mission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """Serve the stored Folium HTML map for a mission."""
    from fastapi.responses import FileResponse
    backend_root = Path(__file__).resolve().parents[2]
    map_path = backend_root / "maps" / f"{mission_id}_map.html"
    if not os.path.exists(map_path):
        raise HTTPException(status_code=404, detail="Map not generated yet")
    return FileResponse(map_path, media_type="text/html")


@router.post("/{mission_id}/upload-plan")
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
