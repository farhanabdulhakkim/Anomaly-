"""
config.py — Central configuration for the Precision Agriculture Drone System.

All field parameters, grid settings, and ML/anomaly simulation knobs live here.
Replace ANOMALY_MODE with "model" and supply a model loader to switch from
simulation to real CNN predictions.
"""

# ─── Field & Reference Coordinates ────────────────────────────────────────────
# Anchor point (south-west corner of the paddy field, Erode, Tamil Nadu).
FIELD_BASE_LAT = 11.3390          # degrees N
FIELD_BASE_LON = 77.7195          # degrees E

# Approximate field extent (metres).  Adjust to your actual field size.
FIELD_WIDTH_M  = 200.0            # East-West extent
FIELD_HEIGHT_M = 200.0            # North-South extent

# ─── Grid System ──────────────────────────────────────────────────────────────
CELL_SIZE_M = 10                  # Each grid cell = 10 m × 10 m

# ─── Coordinate Conversion Constants ──────────────────────────────────────────
# At ~11 °N these are accurate to < 0.1 %.
METRES_PER_DEG_LAT = 110_540.0    # 1° latitude  ≈ 110,540 m
METRES_PER_DEG_LON = 109_290.0    # 1° longitude ≈ 111,320 × cos(11°) ≈ 109,290 m

# ─── Anomaly Simulation ────────────────────────────────────────────────────────
# Set to "random", "rule_based", or "model".
ANOMALY_MODE = "rule_based"

# Probability that a given grid cell contains an anomaly (random mode).
ANOMALY_PROBABILITY = 0.25

# Random seed — ensures reproducible simulations.
RANDOM_SEED = 42

# Rule-based: cells whose normalised altitude std-dev exceeds this are flagged.
# Calibrated to the dataset: cell std values range 0.0 – 0.024; top ~25% flagged.
ALTITUDE_ANOMALY_THRESHOLD = 0.012  # relative (0–1 scale after normalisation)

# ─── Visualisation ─────────────────────────────────────────────────────────────
# Leaflet tile layer — swap for a satellite layer if desired.
TILE_URL     = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_ATTRIB  = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
MAP_ZOOM     = 19

# Grid cell colour thresholds (anomaly count per cell).
COLOR_NORMAL  = "#00C853"   # green  — 0 anomalies
COLOR_LOW     = "#FFD600"   # amber  — 1 anomaly
COLOR_MED     = "#FF6D00"   # orange — 2 anomalies
COLOR_HIGH    = "#D50000"   # red    — ≥ 3 anomalies

# ─── I/O ──────────────────────────────────────────────────────────────────────
INPUT_FILE   = "ardupilot_log.csv"
OUTPUT_HTML  = "output/field_map.html"
OUTPUT_JSON  = "output/field_data.json"

# ─── Flask (optional back-end) ────────────────────────────────────────────────
FLASK_HOST   = "0.0.0.0"
FLASK_PORT   = 5000
FLASK_DEBUG  = True
