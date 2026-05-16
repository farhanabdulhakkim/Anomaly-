# System Architecture

---

## Overview

The platform has three layers:

1. **CLI Pipeline** — standalone Python scripts for quick local processing
2. **Production Backend** — FastAPI + PostgreSQL + PostGIS for persistent multi-user analytics
3. **React Frontend** — dashboard for field management, mission uploads, and map visualisation

---

## Dual Detection Pipeline

### Pipeline A — GPS Telemetry (Rule-Based / Random)

```
drone_flight_with_timestamp.xls  or  ardupilot_log.csv
     |
     v
mission_service._load_telemetry()
     |  Reads XLS/CSV directly
     |  Falls back to logparser.build_clean_dataset() for ArduPilot CSV
     v
mission_service._assign_grid_indices()
     |  Maps GPS points onto field's permanent 10m x 10m grid
     |  Uses field origin_lat / origin_lon — never recomputed
     v
detection/detectors.py
     |  RuleBasedDetector  — altitude variance per cell > threshold
     |  RandomDetector     — probability-based (UI testing)
     |  CNNDetector        — stub for ResNet/EfficientNet/YOLOv8
     v
PostgreSQL
     |  telemetry_points, anomalies, analytics_summary
     v
GET /anomalies/geojson  →  React Leaflet grid map
```

### Pipeline B — CNN Video (PatchCNN)

```
flight.mp4  +  ardupilot_log.csv
     |
     v
POST /upload-video
     |
     v
anomaly.py
     |  Extracts frames at 1 FPS
     |  Runs PatchCNN on 17x17 patches (stride=8)
     |  Flags frames where hybrid_ratio > 1% or max_conf > 0.55
     |  Maps anomaly frames to GPS coordinates via timestamp interpolation
     v
final_log.py
     |  Parses ArduPilot CSV (POS + GPS + CMD messages)
     |  Builds Folium map:
     |    - Actual GPS path (POS log, red)
     |    - Raw GPS fixes (orange, dashed)
     |    - Planned mission path (CMD waypoints, yellow)
     |    - Anomaly detection markers (orange circles)
     |    - 2m x 2m anomaly heatmap grid
     v
/app/maps/{mission_id}_map.html  (stored server-side)
     v
GET /map-html  →  React iframe (CNN Folium Map tab)
```

---

## Backend Architecture

```
HTTP Request
     |
     v
FastAPI Router (app/api/)
     |  auth.py       — register, login, JWT
     |  fields.py     — CRUD + grid generation
     |  missions.py   — telemetry, video, plan uploads
     |  analytics.py  — trend endpoint
     v
Service Layer (app/services/)
     |  field_service.py    — boundary → grid cells
     |  mission_service.py  — telemetry pipeline orchestration
     v
Repository Layer (app/repositories/)
     |  All database queries via SQLAlchemy async ORM
     v
PostgreSQL 16 + PostGIS 3.4
     |  7 tables, GIST indexes on all geometry columns
```

---

## Frontend Architecture

```
React + Vite + Tailwind CSS
     |
     ├── Login.jsx           JWT login, stores token in localStorage
     ├── Dashboard.jsx       Field list + create field modal
     ├── FieldDetail.jsx     Mission list + 3-panel upload workflow
     │     Panel 1: Upload autopilot plan (.waypoints/.plan)
     │     Panel 2: Upload GPS telemetry (.xls/.csv) → rule-based pipeline
     │     Panel 3: Upload video (.mp4) + CSV → CNN pipeline
     └── MissionMap.jsx      Two-tab map view
           Tab 1: GPS Grid Map  — React Leaflet + GeoJSON grid overlay
           Tab 2: CNN Folium Map — iframe → /map-html endpoint
```

---

## CNN Model (PatchCNN)

```
Input: 17x17x3 RGB patch from drone frame
     |
     v
Conv2d(3→32, 3x3) + ReLU + MaxPool2d(2)
     |
     v
Conv2d(32→64, 3x3) + ReLU + MaxPool2d(2)
     |
     v
Conv2d(64→128, 3x3) + ReLU
     |
     v
Flatten → Linear(2048→128) → ReLU → Linear(128→2)
     |
     v
Softmax → class 0 (normal) / class 1 (hybrid/off-type)
```

Trained on paddy field image patches with binary masks.
Weights stored in `backend/patch_cnn_model.pth`.

---

## Anomaly Detection Abstraction (Telemetry Pipeline)

```python
BaseAnomalyDetector (abstract)
    |
    |── RuleBasedDetector    altitude variance > threshold
    |── RandomDetector       random labelling (UI testing)
    └── CNNDetector          stub — plug in your model
```

To add a new model:
1. Subclass `BaseAnomalyDetector`
2. Implement `detect(df) -> pd.DataFrame`
3. Register in `DetectorFactory.get()`
4. Set `anomaly_mode = "model"` on the mission

---

## Permanent Grid Strategy

```
Field created
     |
     v
Grid cells generated (n_rows x n_cols polygons)
     |
     v
Stored in grid_cells table (permanent, never regenerated)
     |
     v
Mission 1 → references same grid_cells by (row, col)
Mission 2 → references same grid_cells by (row, col)
Mission N → references same grid_cells by (row, col)
```

Grid(row=10, col=5) for Field X is identical across all missions.
Anomaly counts are stored per-mission in the `anomalies` table.

---

## Temporal Analytics

```
Mission 1 (April)    → analytics_summary (prev=null, reduction=null)
     |
     v
Mission 2 (May)      → analytics_summary (prev=Mission1, reduction=62.7%)
     |
     v
Mission 3 (June)     → analytics_summary (prev=Mission2, reduction=15.2%)
```

The trend endpoint returns all missions ordered by flight_date for charting.

---

## Coordinate Handling

Raw telemetry from the XLS file has non-standard coordinates:
- Latitude ~77 (valid range: -90 to 90)
- Longitude ~405 (valid range: -180 to 180)

`mission_service._load_telemetry()` detects this and remaps both columns
onto a real GPS bounding box centred on the configured field origin
(Erode, Tamil Nadu by default). Real GPS data passes through unchanged.

---

## Database Migrations

| Revision | Description |
|----------|-------------|
| 0001 | Initial schema — all 7 tables |
| 0002 | Add `waypoint_filename`, `waypoint_raw` to missions |

Run via: `docker compose exec api alembic upgrade head`
