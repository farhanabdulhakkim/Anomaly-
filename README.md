# 🌾 Precision Agriculture — Drone Anomaly Detection System

Grid-based geospatial visualisation of off-type paddy plant anomalies
detected from drone telemetry, built entirely with open-source Python tools.

---

## System Architecture

```
drone_flight.csv / .xls
        │
        ▼
┌─────────────────────┐
│  data_processor.py  │  Load, normalise GPS, compute timing
└────────┬────────────┘
         │  DataFrame: lat, lon, altitude, speed, elapsed_s
         ▼
┌─────────────────────┐
│   grid_engine.py    │  Assign 10m×10m grid indices (Haversine-calibrated)
└────────┬────────────┘
         │  DataFrame + grid_row, grid_col columns
         ▼
┌──────────────────────────┐
│  anomaly_simulator.py    │  Rule-based / Random / CNN model detection
└────────┬─────────────────┘
         │  DataFrame + anomaly flag + summary dict
         ▼
┌─────────────────────┐
│  map_generator.py   │  Build GeoJSON → inject into Leaflet.js HTML
└────────┬────────────┘
         │
         ▼
   output/field_map.html   ← open in any browser, no server required
         │
   (optional)
         ▼
┌─────────────────────┐
│      app.py         │  Flask server + REST API
└─────────────────────┘
```

---

## Project Structure

```
agri_drone_vision/
├── config.py              ← All tuneable parameters (field size, colours, mode)
├── data_processor.py      ← GPS loading, normalisation, timing
├── grid_engine.py         ← 10m × 10m grid, coordinate conversion, cell geometry
├── anomaly_simulator.py   ← Pluggable anomaly detection (random / rule / ML)
├── map_generator.py       ← GeoJSON builder + Leaflet.js HTML generator
├── main.py                ← CLI entry point / importable pipeline function
├── app.py                 ← Optional Flask backend + REST API
├── requirements.txt
├── sample_data.csv        ← Well-formed sample with standard WGS-84 coords
└── output/
    └── field_map.html     ← Generated interactive map
```

---

## Quick Start

### 1 — Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Run the pipeline (standalone, no server)

```bash
# Using the uploaded drone telemetry file
python main.py drone_flight_with_timestamp__1_.xls

# Using the bundled sample CSV
python main.py sample_data.csv

# Open in browser automatically
python main.py drone_flight_with_timestamp__1_.xls --open

# Override anomaly mode
python main.py drone_flight_with_timestamp__1_.xls --mode random

# Custom cell size (5m × 5m grid)
python main.py drone_flight_with_timestamp__1_.xls --cell-size 5
```

The output is a **single self-contained HTML file** (`output/field_map.html`).
Open it in any browser — no web server required.

### 3 — (Optional) Run the Flask server

```bash
python app.py
# → http://localhost:5000          interactive map
# → http://localhost:5000/api/anomalies   JSON anomaly list
```

---

## Input Format

Your CSV / XLS file needs these five columns (names are case-insensitive):

| Column      | Type     | Description                              |
|-------------|----------|------------------------------------------|
| `Timestamp` | datetime | ISO 8601 string, e.g. `2026-03-03 15:00:01.234` |
| `Latitude`  | float    | WGS-84 decimal degrees (or raw sensor)  |
| `Longitude` | float    | WGS-84 decimal degrees (or raw sensor)  |
| `Altitude`  | float    | Metres AGL (above ground level)          |
| `Speed`     | float    | Metres per second                        |

**Non-standard coordinates:** If Latitude/Longitude are outside ±90/±180
(e.g. raw sensor values), `data_processor.py` automatically remaps them
onto a realistic GPS bounding box centred on the configured field origin.
A note about this is printed during the run.

---

## Configuration (`config.py`)

| Parameter                     | Default       | Description                            |
|-------------------------------|---------------|----------------------------------------|
| `FIELD_BASE_LAT/LON`          | 11.3390, 77.7195 | SW corner of paddy field (Erode, TN) |
| `FIELD_WIDTH_M / HEIGHT_M`    | 200 m         | Field extent for coordinate remapping  |
| `CELL_SIZE_M`                 | 10            | Grid resolution in metres              |
| `ANOMALY_MODE`                | `rule_based`  | `random`, `rule_based`, or `model`     |
| `ANOMALY_PROBABILITY`         | 0.25          | Used in `random` mode only             |
| `ALTITUDE_ANOMALY_THRESHOLD`  | 0.012         | Normalised std-dev threshold for rule  |
| `COLOR_NORMAL/LOW/MED/HIGH`   | green→red     | Cell fill colours by anomaly count     |

---

## Anomaly Detection Modes

### `rule_based` (default)
Flags grid cells where altitude variability (canopy height proxy) exceeds
a calibrated threshold. Also flags individual altitude outliers (> 2σ from
the flight mean). This is the most realistic simulation before the CNN model
is ready.

### `random`
Each GPS point is randomly labelled anomalous with probability
`config.ANOMALY_PROBABILITY`. Useful for UI testing.

### `model` — plug in your CNN
1. Set `ANOMALY_MODE = "model"` in `config.py`
2. Implement `load_model_predictions(df)` in `anomaly_simulator.py`:

```python
def load_model_predictions(df: pd.DataFrame) -> dict:
    import tensorflow as tf
    model   = tf.keras.models.load_model("cnn_paddy_v1.h5")
    patches = load_image_patches(df)           # your image loading logic
    preds   = (model.predict(patches) > 0.5)   # binary output
    result  = defaultdict(int)
    for i, row in df.iterrows():
        if preds[i]:
            result[(row["grid_row"], row["grid_col"])] += 1
    return dict(result)
```

No other file needs to change.

---

## Map Features

| Feature                  | Description                                         |
|--------------------------|-----------------------------------------------------|
| **Grid overlay**         | 10m×10m cells, colour-coded by anomaly count        |
| **Drone flight path**    | Dashed blue polyline with start/end markers         |
| **Anomaly points**       | Red dots at exact GPS coordinates of detections     |
| **Layer toggles**        | Show/hide grid, path, and anomaly points            |
| **Cell inspector**       | Click any cell → row/col, count, density in sidebar |
| **Drone animation**      | Play button animates the drone along its flight path|
| **Hover highlighting**   | Mouse-over outlines the hovered cell                |

---

## REST API (Flask mode)

| Endpoint          | Method | Description                           |
|-------------------|--------|---------------------------------------|
| `/`               | GET    | Serve the interactive HTML map        |
| `/api/status`     | GET    | Health check + current config         |
| `/api/anomalies`  | GET    | JSON list of anomalous cells sorted by count |
| `/api/grid`       | GET    | Full GeoJSON of all grid cells        |
| `/api/run`        | POST   | Re-run pipeline (`{"mode":"random"}`) |
| `/api/upload`     | POST   | Upload a new telemetry file           |

---

## Upgrading to UTM Projection (large fields > 5 km)

For fields larger than 5 km, replace the equirectangular approximation
with a full UTM projection by uncommenting `pyproj` in `requirements.txt`
and swapping `assign_grid_indices` in `grid_engine.py`:

```python
from pyproj import Transformer
def assign_grid_indices(df, cell_m=config.CELL_SIZE_M):
    t = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
    east, north = t.transform(df["lon"].values, df["lat"].values)
    east_origin  = east.min()  - cell_m / 2
    north_origin = north.min() - cell_m / 2
    df = df.copy()
    df["grid_col"]   = ((east  - east_origin)  / cell_m).astype(int)
    df["grid_row"]   = ((north - north_origin) / cell_m).astype(int)
    df["origin_lat"] = ...   # back-project with t.transform(..., direction="INVERSE")
    df["origin_lon"] = ...
    df["cell_m"]     = cell_m
    return df
```

---

## Adding Real-Time Streaming

1. Have the drone publish GPS + prediction events to an MQTT topic or WebSocket.
2. Add a `/api/stream` SSE endpoint in `app.py` that yields new points.
3. In the Leaflet HTML, open an `EventSource("/api/stream")` and call
   `droneMarker.setLatLng(...)` on each event — the animation framework
   is already in place.

---

## Future Roadmap

- [ ] Replace simulated anomalies with ResNet/EfficientNet CNN predictions
- [ ] Real-time WebSocket streaming from drone telemetry
- [ ] Heatmap layer (Leaflet.heat plugin — single import)
- [ ] Export detected anomaly zones as Shapefile / KML for field crews
- [ ] Multi-flight comparison (overlay two flight sessions)
- [ ] Integration with NDVI raster overlays
