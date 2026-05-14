# Backend — FastAPI + PostGIS Platform

Production-grade REST API for the Precision Agriculture Drone Analytics Platform.

---

## Setup

### Prerequisites
- Docker Desktop
- Python 3.11+

### Run with Docker (recommended)

```bash
# From project root
copy backend\.env.example backend\.env
# Edit backend\.env — set SECRET_KEY

docker-compose up --build
```

API: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

### Run locally (without Docker)

```bash
cd backend
pip install -r requirements.txt

# Start PostgreSQL with PostGIS separately, then:
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://agri_user:agri_pass@db:5432/agri_db` |
| `SECRET_KEY` | JWT signing key (change this) | — |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry | `60` |
| `ENVIRONMENT` | `development` or `production` | `development` |

---

## Folder Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── auth.py         Register, login, JWT
│   │   ├── fields.py       Field CRUD + grid GeoJSON
│   │   ├── missions.py     Mission management + telemetry upload
│   │   └── analytics.py    Trend and hotspot analytics
│   ├── core/
│   │   ├── config.py       Pydantic settings
│   │   └── security.py     Password hashing, JWT encode/decode
│   ├── db/
│   │   └── session.py      Async SQLAlchemy engine + session
│   ├── models/             SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── field.py        POLYGON boundary
│   │   ├── grid_cell.py    Permanent POLYGON cells
│   │   ├── mission.py      LINESTRING flight path
│   │   ├── telemetry.py    POINT observations
│   │   ├── anomaly.py      Per-cell anomaly counts
│   │   └── analytics.py    Aggregated mission stats
│   ├── schemas/
│   │   └── schemas.py      All Pydantic request/response models
│   ├── services/
│   │   ├── field_service.py    Field creation + permanent grid generation
│   │   └── mission_service.py  Telemetry processing + anomaly detection
│   ├── repositories/
│   │   └── repositories.py     All database query functions
│   ├── detection/
│   │   └── detectors.py        BaseAnomalyDetector, RuleBased, Random, CNN stub
│   └── main.py                 FastAPI app + router registration
├── alembic/
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   └── env.py
├── alembic.ini
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Key Design Decisions

### Permanent Grid
When a field is created, its 10m x 10m grid cells are generated **once** and stored permanently in `grid_cells`. All future missions reference the same cells by `(row, col)` — the grid never shifts between missions.

### Spatial Storage
All geometries are stored in PostGIS with SRID 4326 (WGS-84):
- Field boundary → `POLYGON`
- Grid cells → `POLYGON`
- Flight path → `LINESTRING`
- Telemetry points → `POINT`

### Anomaly Detection Abstraction
```python
# To plug in a CNN model:
class MyCNNDetector(BaseAnomalyDetector):
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        # load model, run inference, set df["anomaly"]
        return df

# Register in DetectorFactory.get()
```

---

## Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Rollback one step
alembic downgrade -1
```

---

## Example API Flow

```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@farm.com","full_name":"Farmer","password":"pass123"}'

# 2. Login
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=user@farm.com&password=pass123"

# 3. Create field (use token from step 2)
curl -X POST http://localhost:8000/api/fields \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Field 1","cell_size_m":10,"boundary_geojson":{...}}'

# 4. Upload telemetry
curl -X POST http://localhost:8000/api/fields/{field_id}/missions/{mission_id}/upload-telemetry \
  -H "Authorization: Bearer <token>" \
  -F "file=@drone_flight_with_timestamp.xls"
```
