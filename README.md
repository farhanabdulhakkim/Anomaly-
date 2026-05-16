# Precision Agriculture Drone Analytics Platform

A production-grade drone-based anomaly detection system for paddy fields.
Detects off-type plants using GPS telemetry and CNN video analysis, maps them
onto a 10m x 10m grid, and provides a persistent REST API backed by
PostgreSQL + PostGIS with a React dashboard frontend.

---

## Architecture

```
Drone Video (.mp4) + ArduPilot CSV
        |
        v
  anomaly.py            PatchCNN frame-by-frame detection
        |
        v
  final_log.py          Folium map with GPS path + anomaly grid
        |
        v
  ┌─────────────────────────────────────────┐
  │                                         │
  │  Drone Telemetry (XLS/CSV)              │
  │          |                              │
  │          v                              │
  │    logparser.py     ArduPilot CSV parse │
  │          |                              │
  │          v                              │
  │    data_processor.py  Coord normalise   │
  │          |                              │
  │          v                              │
  │    grid_engine.py   10m x 10m grid      │
  │          |                              │
  │          v                              │
  │    anomaly_simulator.py  Rule/Random    │
  │          |                              │
  │          v                              │
  │    map_generator.py  Folium HTML map    │
  └─────────────────────────────────────────┘
        |
        v
  backend/              FastAPI + PostgreSQL + PostGIS
        |
        v
  frontend/             React + Vite + Tailwind + Leaflet
```

---

## Project Structure

```
miniproject/
├── backend/                    FastAPI production backend
│   ├── app/
│   │   ├── api/                Route handlers (auth, fields, missions, analytics)
│   │   ├── core/               JWT security, settings
│   │   ├── db/                 Async SQLAlchemy session
│   │   ├── models/             ORM models with PostGIS geometry
│   │   ├── schemas/            Pydantic request/response schemas
│   │   ├── services/           Business logic layer
│   │   ├── repositories/       Database query layer
│   │   ├── detection/          Pluggable anomaly detector abstraction
│   │   └── main.py             FastAPI app entry point
│   ├── alembic/                Database migrations
│   │   └── versions/
│   │       ├── 0001_initial_schema.py
│   │       └── 0002_add_waypoint_columns.py
│   ├── anomaly.py              CNN video pipeline (PatchCNN)
│   ├── final_log.py            Folium map builder
│   ├── model.py                PatchCNN architecture
│   ├── patch_cnn_model.pth     Trained CNN weights
│   ├── logparser.py            ArduPilot CSV log parser
│   ├── maps/                   Generated Folium HTML maps (runtime)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   React + Vite dashboard
│   ├── src/
│   │   ├── api/                Axios client + service functions
│   │   ├── components/         StatCard, TrendChart
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx   Field management
│   │   │   ├── FieldDetail.jsx Mission management + uploads
│   │   │   └── MissionMap.jsx  Leaflet map + Folium map tabs
│   │   └── App.jsx
│   ├── Dockerfile
│   └── package.json
├── logparser.py                ArduPilot CSV log parser (CLI)
├── convert_to_ardupilot.py     XLS to ArduPilot CSV converter
├── data_processor.py           GPS loading and coordinate normalisation
├── grid_engine.py              10m x 10m grid engine
├── anomaly_simulator.py        Anomaly detection (rule/random/model)
├── map_generator.py            Folium map generator
├── main.py                     CLI pipeline entry point
├── app.py                      Legacy Flask server
├── config.py                   Pipeline configuration
├── docker-compose.yml          PostgreSQL + PostGIS + API + Frontend
└── README.md
```

---

## Quick Start

### Option A — CLI Pipeline (no database)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py drone_flight_with_timestamp.xls --mode rule_based
# Opens output/field_map.html
```

### Option B — Full Platform (Docker)

```bash
cd backend
copy .env.example .env
# Edit .env — set SECRET_KEY to a random string

cd ..
docker compose up --build
# API:      http://localhost:8000
# Frontend: http://localhost:3000
# Swagger:  http://localhost:8000/docs
```

---

## Frontend Workflow

After login and field creation:

1. Create a mission on the Field Detail page
2. Panel 1 — upload autopilot plan (`.waypoints` / `.plan`) — optional
3. Panel 2 — upload GPS telemetry (`.xls` / `.csv`) → rule-based/random anomaly detection
4. Panel 3 — upload drone video (`.mp4`) + ArduPilot CSV → CNN pipeline → Folium map
5. Click "View Map & Analytics" to open the mission map with two tabs:
   - GPS Grid Map — Leaflet interactive grid coloured by anomaly density
   - CNN Folium Map — Folium HTML from the CNN video pipeline

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register user |
| POST | `/api/auth/login` | Login, get JWT |
| GET | `/api/auth/me` | Current user |
| POST | `/api/fields` | Create field + generate permanent grid |
| GET | `/api/fields` | List all fields |
| GET | `/api/fields/{id}` | Get field details |
| PATCH | `/api/fields/{id}` | Update field metadata |
| GET | `/api/fields/{id}/grid/geojson` | Field grid as GeoJSON |
| POST | `/api/fields/{id}/missions` | Create mission |
| GET | `/api/fields/{id}/missions` | List missions |
| POST | `/api/fields/{id}/missions/{id}/upload-telemetry` | Upload GPS log + run pipeline |
| POST | `/api/fields/{id}/missions/{id}/upload-video` | Upload video + CSV → CNN pipeline |
| POST | `/api/fields/{id}/missions/{id}/upload-plan` | Upload autopilot waypoint plan |
| GET | `/api/fields/{id}/missions/{id}/plan` | Get stored waypoint plan |
| GET | `/api/fields/{id}/missions/{id}/map-html` | Serve Folium HTML map |
| GET | `/api/fields/{id}/missions/{id}/flight-path` | Flight path as GeoJSON |
| GET | `/api/fields/{id}/missions/{id}/analytics` | Mission analytics |
| GET | `/api/fields/{id}/missions/{id}/anomalies/geojson` | Anomaly GeoJSON |
| GET | `/api/fields/{id}/missions/compare/{a}/{b}` | Compare two missions |
| GET | `/api/analytics/fields/{id}/trend` | Anomaly trend over time |

---

## Database Schema

| Table | Description |
|-------|-------------|
| `users` | Authenticated users |
| `fields` | Agricultural fields with PostGIS POLYGON boundary |
| `grid_cells` | Permanent 10m x 10m cells per field (PostGIS POLYGON) |
| `missions` | Drone flights with PostGIS LINESTRING path |
| `telemetry_points` | GPS observations with PostGIS POINT geometry |
| `anomalies` | Anomaly counts per mission per grid cell |
| `analytics_summary` | Aggregated stats + mission-to-mission comparison |

---

## Anomaly Detection Modes

| Mode | Description |
|------|-------------|
| `rule_based` | Altitude variance per cell as canopy height proxy |
| `random` | Random labelling for UI testing |
| `model` | CNN stub — plug in ResNet/EfficientNet/YOLOv8 |
| CNN video | PatchCNN on drone video frames via `upload-video` endpoint |

---

## Tech Stack

- Python 3.11
- FastAPI + Uvicorn
- PostgreSQL 16 + PostGIS 3.4
- SQLAlchemy 2.0 (async) + GeoAlchemy2
- Alembic migrations
- PyTorch + OpenCV (CNN video pipeline)
- Folium (map visualisation)
- React 18 + Vite + Tailwind CSS
- React Leaflet (interactive grid map)
- Docker + docker-compose
- JWT authentication (python-jose + passlib)
