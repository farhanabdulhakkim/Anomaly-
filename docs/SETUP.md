# Setup & Deployment Guide

---

## Prerequisites

- Python 3.11+
- Docker Desktop
- Node.js 18+ (only for running frontend outside Docker)
- Git

---

## Option A — CLI Pipeline (no database)

For quick local processing without Docker.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

# Run pipeline on XLS telemetry
python main.py drone_flight_with_timestamp.xls --mode rule_based

# Open the map
start output/field_map.html   # Windows
# open output/field_map.html  # Mac
```

### CLI Options
```bash
python main.py <file>                   # default: rule_based mode
python main.py <file> --mode random     # random anomaly mode
python main.py <file> --mode rule_based
python main.py <file> --cell-size 5    # 5m x 5m grid
python main.py <file> --open           # auto-open browser
```

### Legacy Flask Server
```bash
python app.py
# API + map at http://localhost:5000
```

---

## Option B — Full Platform (Docker)

### 1. Configure environment
```bash
cd backend
copy .env.example .env    # Windows
# cp .env.example .env    # Linux/Mac
```

Edit `backend/.env`:
```
DATABASE_URL=postgresql+asyncpg://agri_user:agri_pass@db:5432/agri_db
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ENVIRONMENT=development
```

### 2. Start all containers
```bash
# From project root
docker compose up --build
```

This will:
- Pull PostgreSQL 16 + PostGIS 3.4 image
- Build the FastAPI container (installs torch, opencv, pandas, etc.)
- Build the React frontend container
- Run `alembic upgrade head` (creates all tables + applies migrations)
- Start API on http://localhost:8000
- Start frontend on http://localhost:3000

> Note: First build takes several minutes due to PyTorch installation.

### 3. Verify
```
http://localhost:3000          → React frontend
http://localhost:8000/health   → {"status": "ok"}
http://localhost:8000/docs     → Swagger UI
```

### 4. Stop
```bash
docker compose down            # stop containers
docker compose down -v         # stop + delete database volume
```

---

## Frontend Workflow

1. Open `http://localhost:3000` and register/login
2. Create a field (uses default Erode, TN boundary)
3. Open the field → create a mission
4. Upload files using the 3-panel workflow:
   - Panel 1: `.waypoints` / `.plan` autopilot file (optional)
   - Panel 2: `.xls` or `.csv` GPS telemetry → rule-based detection
   - Panel 3: `.mp4` video + ArduPilot `.csv` → CNN detection
5. Click "View Map & Analytics" to see results

---

## Database Migrations

```bash
# Apply all pending migrations (runs automatically on startup)
docker compose exec api alembic upgrade head

# Create a new migration after model changes
docker compose exec api alembic revision --autogenerate -m "description"

# Check current migration version
docker compose exec api alembic current

# View migration history
docker compose exec api alembic history
```

---

## Verify Database Tables

```bash
docker exec -it agri_db psql -U agri_user -d agri_db -c "\dt"
```

Expected output:
```
 Schema |       Name        | Type  |   Owner
--------+-------------------+-------+-----------
 public | alembic_version   | table | agri_user
 public | analytics_summary | table | agri_user
 public | anomalies         | table | agri_user
 public | fields            | table | agri_user
 public | grid_cells        | table | agri_user
 public | missions          | table | agri_user
 public | telemetry_points  | table | agri_user
 public | users             | table | agri_user
```

---

## Rebuild After Code Changes

```bash
# Python/JS file changes — auto-reloaded (no action needed)

# requirements.txt or package.json changes
docker compose build --no-cache api
docker compose up

# Full clean rebuild
docker compose down
docker compose build --no-cache
docker compose up
```

---

## Running Frontend Outside Docker

```bash
cd frontend
npm install
npm run dev
# Runs at http://localhost:5173
```

Make sure the API is running at `http://localhost:8000` (via Docker or locally).

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `column missions.waypoint_filename does not exist` | Run `docker compose exec api alembic upgrade head` |
| `service "agri_api" is not running` | Use service name `api` not container name: `docker compose exec api ...` |
| `No module named 'logparser'` | Ensure `logparser.py` is mounted: check `docker-compose.yml` volume for `./logparser.py:/app/logparser.py` |
| `pandas.errors.ParserError: Expected 72 fields` | ArduPilot CSV — handled automatically by `_try_load_csv()` fallback |
| Upload failed (500) | Check `docker compose logs api --tail=30` for the actual exception |
| `Name or service not known` | Use `db` not `localhost` in DATABASE_URL inside containers |
| `bcrypt` version error | Pin `bcrypt==4.0.1` in requirements.txt |
| Frontend shows blank page | Check `docker compose logs frontend` — may need `npm install` rebuild |
| CNN pipeline slow | Expected — PyTorch runs on CPU in Docker. GPU support requires `nvidia-docker` |
