# Setup & Deployment Guide

---

## Prerequisites

- Python 3.11+
- Docker Desktop
- Git

---

## Option A — CLI Pipeline (no database)

For quick local processing without Docker.

```bash
# Clone and setup
git clone https://github.com/harishvardhan27/Anamoly_Detection
cd Anamoly_Detection

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

# Run pipeline
python main.py drone_flight_with_timestamp.xls --mode rule_based

# Open the map
start output/field_map.html   # Windows
# open output/field_map.html  # Mac
```

### CLI Options
```bash
python main.py <file>                  # default: rule_based mode
python main.py <file> --mode random    # random anomaly mode
python main.py <file> --mode rule_based
python main.py <file> --cell-size 5   # 5m x 5m grid
python main.py <file> --open          # auto-open browser
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

### 2. Start containers
```bash
# From project root
docker-compose up --build
```

This will:
- Pull PostgreSQL 16 + PostGIS 3.4 image
- Build the FastAPI container
- Run `alembic upgrade head` (creates all 7 tables)
- Start API on http://localhost:8000

### 3. Verify
```
http://localhost:8000/health   → {"status": "ok"}
http://localhost:8000/docs     → Swagger UI
```

### 4. Stop
```bash
docker-compose down            # stop containers
docker-compose down -v         # stop + delete database volume
```

---

## Database Migrations

```bash
# Apply all pending migrations
docker exec agri_api alembic upgrade head

# Create a new migration after model changes
docker exec agri_api alembic revision --autogenerate -m "add new column"

# Check current migration version
docker exec agri_api alembic current
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
# Python file changes — auto-reloaded by uvicorn (no action needed)

# requirements.txt changes
docker-compose build --no-cache api
docker-compose up

# Full clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No module named 'logparser'` | logparser is not inside backend/ — fixed in mission_service.py |
| `Name or service not known` | Change `localhost` to `db` in DATABASE_URL |
| `bcrypt` version error | Pin `bcrypt==4.0.1` in requirements.txt |
| `AmbiguousForeignKeysError` | Add `foreign_keys=` to SQLAlchemy relationship |
| `version` attribute obsolete warning | Remove `version:` from docker-compose.yml (harmless) |
| 500 on register | Check `docker logs agri_api --tail 30` |
