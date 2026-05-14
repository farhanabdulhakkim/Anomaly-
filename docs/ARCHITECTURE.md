# System Architecture

---

## Overview

The platform has two layers:

1. **CLI Pipeline** — standalone Python scripts for quick local processing
2. **Production Backend** — FastAPI + PostgreSQL + PostGIS for persistent multi-user analytics

---

## Pipeline Flow

```
Drone Flight
     |
     v
drone_flight_with_timestamp.xls
     |
     v
convert_to_ardupilot.py
     |  Converts raw XLS to ArduPilot CSV format
     |  (GPS + ATT message rows)
     v
ardupilot_log.csv
     |
     v
logparser.py
     |  Extracts GPS (Lat, Lon, Alt, Speed)
     |  Extracts ATT (Roll, Pitch, Yaw)
     |  Merges by nearest timestamp (500ms tolerance)
     v
data_processor.py
     |  Detects non-standard coordinates
     |  Remaps onto real GPS field bbox
     |  Computes elapsed_s
     v
grid_engine.py
     |  Assigns grid_row, grid_col per point
     |  Haversine-calibrated equirectangular projection
     |  10m x 10m cells
     v
anomaly_simulator.py / detection/detectors.py
     |  RuleBasedDetector  — altitude variance threshold
     |  RandomDetector     — probability-based (testing)
     |  CNNDetector        — plug in ResNet/EfficientNet/YOLO
     v
map_generator.py
     |  Folium map with 3 layers:
     |  - Grid overlay (colour-coded by anomaly density)
     |  - Animated flight path (AntPath)
     |  - Anomaly points (red CircleMarkers)
     v
output/field_map.html
```

---

## Backend Architecture

```
HTTP Request
     |
     v
FastAPI Router (app/api/)
     |
     v
Service Layer (app/services/)
     |  Business logic
     |  Calls pipeline modules
     |  Builds PostGIS geometries
     |
     v
Repository Layer (app/repositories/)
     |  All database queries
     |  SQLAlchemy async ORM
     |
     v
PostgreSQL + PostGIS
     |  7 tables with spatial indexes
     |  GIST indexes on all geometry columns
```

---

## Anomaly Detection Abstraction

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
Stored in grid_cells table (permanent)
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

The raw telemetry has non-standard coordinates:
- Latitude ~77 (valid range: -90 to 90)
- Longitude ~405 (valid range: -180 to 180)

`data_processor.py` detects this and remaps both columns onto a real GPS
bounding box centred on the configured field origin (Erode, Tamil Nadu).

When real GPS data is available, it passes through unchanged.

---

## Future Extensions

| Feature | Where to add |
|---------|-------------|
| CNN model | `backend/app/detection/detectors.py` — subclass `CNNDetector` |
| WebSocket streaming | `backend/app/api/missions.py` — add SSE endpoint |
| React frontend | Consume GeoJSON endpoints from `/anomalies/geojson` |
| Heatmap layer | `map_generator.py` — add `folium.plugins.HeatMap` |
| UTM projection | `grid_engine.py` — swap equirectangular for pyproj |
| MQTT telemetry | New `app/api/stream.py` router |
