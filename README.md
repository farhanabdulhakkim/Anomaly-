# Precision Agriculture Drone Analytics Platform

A production-grade drone-based anomaly detection system for paddy fields.
Detects off-type plants using GPS telemetry, maps them onto a 10m x 10m grid,
and provides a persistent REST API backed by PostgreSQL + PostGIS.

---

## Architecture

```
Drone Telemetry (XLS/CSV)
        |
        v
  logparser.py          ArduPilot CSV parsing (GPS + ATT messages)
        |
        v
  data_processor.py     Coordinate normalisation + remapping
        |
        v
  grid_engine.py        10m x 10m grid assignment (Haversine-calibrated)
        |
        v
  anomaly_simulator.py  Rule-based / Random / CNN detection
        |
        v
  map_generator.py      Folium interactive HTML map
        |
        v
  backend/              FastAPI + PostgreSQL + PostGIS (persistent platform)
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
│   ├── Dockerfile
│   └── requirements.txt
├── logparser.py                ArduPilot CSV log parser
├── convert_to_ardupilot.py     XLS to ArduPilot CSV converter
├── data_processor.py           GPS loading and coordinate normalisation
├── grid_engine.py              10m x 10m grid engine
├── anomaly_simulator.py        Anomaly detection (rule/random/model)
├── map_generator.py            Folium map generator
├── main.py                     CLI pipeline entry point
├── app.py                      Legacy Flask server
├── config.py                   Pipeline configuration
├── docker-compose.yml          PostgreSQL + PostGIS + API containers
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
# Edit .env and set SECRET_KEY to a random string

cd ..
docker-compose up --build
# API running at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

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
| POST | `/api/fields/{id}/missions/{id}/upload-telemetry` | Upload + process telemetry |
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

---

## Tech Stack

- Python 3.11
- FastAPI + Uvicorn
- PostgreSQL 16 + PostGIS 3.4
- SQLAlchemy 2.0 (async) + GeoAlchemy2
- Alembic migrations
- Folium (map visualisation)
- Docker + docker-compose
- JWT authentication (python-jose + passlib)
