# Database Schema

PostgreSQL 16 + PostGIS 3.4. All geometries use SRID 4326 (WGS-84).

---

## ER Diagram

```
users
  |
  | 1:N
  v
fields ──────────────────────────────────────┐
  |                                          |
  | 1:N (permanent, generated once)          |
  v                                          |
grid_cells <──────────── anomalies           |
                              |              |
                              | N:1          |
                              v              |
                          missions <─────────┘
                              |
                    ┌─────────┴──────────┐
                    v                    v
           telemetry_points     analytics_summary
```

---

## Tables

### users
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| email | VARCHAR(255) UNIQUE | Login email |
| full_name | VARCHAR(255) | |
| hashed_password | VARCHAR(255) | bcrypt hash |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

---

### fields
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| owner_id | UUID FK → users | |
| name | VARCHAR(255) | |
| rice_type | VARCHAR(100) | e.g. IR64, Samba |
| soil_type | VARCHAR(100) | e.g. clay, loam |
| irrigation_type | VARCHAR(100) | e.g. drip, flood |
| area_hectares | FLOAT | |
| planting_date | DATE | |
| cell_size_m | INTEGER | Grid resolution (default 10m) |
| boundary | GEOMETRY(POLYGON, 4326) | GIST indexed |
| origin_lat | FLOAT | SW corner latitude |
| origin_lon | FLOAT | SW corner longitude |
| n_rows | INTEGER | |
| n_cols | INTEGER | |

---

### grid_cells
Permanent cells — generated once per field, never regenerated.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| field_id | UUID FK → fields | |
| row | INTEGER | |
| col | INTEGER | |
| geom | GEOMETRY(POLYGON, 4326) | GIST indexed |
| centre_lat | FLOAT | |
| centre_lon | FLOAT | |
| sw_lat / sw_lon | FLOAT | South-west corner |
| ne_lat / ne_lon | FLOAT | North-east corner |

Unique constraint: `(field_id, row, col)`

---

### missions
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| field_id | UUID FK → fields | |
| name | VARCHAR(255) | |
| drone_model | VARCHAR(100) | |
| flight_altitude_m | FLOAT | |
| anomaly_mode | VARCHAR(20) | rule_based / random / model |
| status | VARCHAR(20) | pending / processing / completed / failed |
| version | INTEGER | |
| flight_path | GEOMETRY(LINESTRING, 4326) | GIST indexed |
| total_points | INTEGER | |
| anomaly_point_count | INTEGER | |
| anomaly_cell_count | INTEGER | |
| duration_s | FLOAT | |
| waypoints | JSON | Mission planner waypoints |
| flight_date | TIMESTAMPTZ | |

---

### telemetry_points
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| mission_id | UUID FK → missions | |
| geom | GEOMETRY(POINT, 4326) | GIST indexed |
| altitude_m | FLOAT | |
| speed_ms | FLOAT | |
| roll_deg | FLOAT | From ATT messages |
| pitch_deg | FLOAT | |
| yaw_deg | FLOAT | |
| elapsed_s | FLOAT | Seconds since flight start |
| grid_row | INTEGER | |
| grid_col | INTEGER | |
| is_anomaly | BOOLEAN | |
| recorded_at | TIMESTAMPTZ | |

---

### anomalies
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| mission_id | UUID FK → missions | |
| grid_cell_id | UUID FK → grid_cells | |
| anomaly_count | INTEGER | |
| total_points | INTEGER | |
| density | FLOAT | anomaly_count / total_points |

Unique constraint: `(mission_id, grid_cell_id)`

---

### analytics_summary
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| mission_id | UUID FK → missions UNIQUE | |
| total_cells | INTEGER | |
| anomaly_cells | INTEGER | |
| clean_cells | INTEGER | |
| total_anomaly_points | INTEGER | |
| avg_anomaly_density | FLOAT | |
| max_anomaly_density | FLOAT | |
| prev_mission_id | UUID FK → missions | For comparison |
| anomaly_reduction_pct | FLOAT | e.g. 62.7 = 62.7% reduction |
| cell_change_count | INTEGER | +/- vs previous mission |
| hotspot_cell_ids | JSON | Recurring anomaly cell IDs |
| computed_at | TIMESTAMPTZ | |

---

## Spatial Indexes

```sql
CREATE INDEX ix_fields_boundary_gist       ON fields           USING GIST (boundary);
CREATE INDEX ix_grid_cells_geom_gist       ON grid_cells       USING GIST (geom);
CREATE INDEX ix_missions_flight_path_gist  ON missions         USING GIST (flight_path);
CREATE INDEX ix_telemetry_geom_gist        ON telemetry_points USING GIST (geom);
```

---

## Example PostGIS Queries

```sql
-- Anomaly cells within 50m of a GPS point
SELECT gc.row, gc.col, a.anomaly_count
FROM grid_cells gc
JOIN anomalies a ON a.grid_cell_id = gc.id
WHERE ST_DWithin(
    gc.geom::geography,
    ST_SetSRID(ST_MakePoint(77.7200, 11.3395), 4326)::geography,
    50
);

-- Fields containing a GPS point
SELECT name FROM fields
WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint(77.7200, 11.3395), 4326));

-- Total anomaly area for a mission (sq metres)
SELECT SUM(ST_Area(gc.geom::geography)) AS anomaly_area_m2
FROM grid_cells gc
JOIN anomalies a ON a.grid_cell_id = gc.id
WHERE a.mission_id = '<mission_id>' AND a.anomaly_count > 0;

-- Recurring hotspot cells across all missions
SELECT gc.row, gc.col, COUNT(DISTINCT a.mission_id) AS mission_count
FROM grid_cells gc
JOIN anomalies a ON a.grid_cell_id = gc.id
WHERE gc.field_id = '<field_id>' AND a.anomaly_count > 0
GROUP BY gc.row, gc.col
ORDER BY mission_count DESC;
```
