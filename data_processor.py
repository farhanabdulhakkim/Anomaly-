"""
data_processor.py — Load raw drone telemetry, normalise coordinates to a
                     realistic GPS field, and expose clean DataFrames.

NOTE on the sample dataset
--------------------------
The uploaded file has:
  • "Latitude"  ≈ 77.0274 – 77.0275  (nearly constant; ~2 m EW spread)
  • "Longitude" ≈ 405.6  – 408.5     (non-standard; likely a sensor metric)

Both columns are remapped onto a realistic paddy-field bounding box centred
near Erode, Tamil Nadu, using the values as *relative position* proxies.
When you swap in a properly-georeferenced dataset the `load_and_preprocess`
function needs no changes — it expects standard (lat, lon) columns and will
use them as-is if they fall within ±90 / ±180.
"""

import math
import pandas as pd
import numpy as np

import config
import logparser


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_standard_gps(lat_series: pd.Series, lon_series: pd.Series) -> bool:
    """Return True if both columns look like valid WGS-84 coordinates."""
    lat_ok = lat_series.between(-90, 90).all()
    lon_ok = lon_series.between(-180, 180).all()
    return lat_ok and lon_ok


def _normalise_to_field(
    raw_lat: pd.Series,
    raw_lon: pd.Series,
    base_lat: float = config.FIELD_BASE_LAT,
    base_lon: float = config.FIELD_BASE_LON,
    width_m: float  = config.FIELD_WIDTH_M,
    height_m: float = config.FIELD_HEIGHT_M,
) -> tuple[pd.Series, pd.Series]:
    """
    Linearly map raw sensor coordinates onto a realistic GPS bounding box.

    The raw_lat values drive the East-West axis (longitude output) and
    raw_lon values drive the North-South axis (latitude output), matching
    the observed data structure where 'Latitude' varies only slightly and
    'Longitude' carries the dominant positional change.
    """
    def _min_max_scale(series: pd.Series) -> pd.Series:
        lo, hi = series.min(), series.max()
        if hi == lo:                              # degenerate — single value
            return pd.Series(np.zeros(len(series)), index=series.index)
        return (series - lo) / (hi - lo)

    lat_norm = _min_max_scale(raw_lat)
    lon_norm = _min_max_scale(raw_lon)

    # Degrees per metre
    deg_per_m_lat = 1.0 / config.METRES_PER_DEG_LAT
    deg_per_m_lon = 1.0 / config.METRES_PER_DEG_LON

    mapped_lat = base_lat + lon_norm * height_m * deg_per_m_lat
    mapped_lon = base_lon + lat_norm * width_m  * deg_per_m_lon

    return mapped_lat, mapped_lon


# ─── Public API ───────────────────────────────────────────────────────────────

def load_raw(filepath: str) -> pd.DataFrame:
    """
    Load telemetry via logparser (ArduPilot CSV) if the file is
    ardupilot_log.csv, otherwise fall back to direct CSV/XLS read.

    Output columns (normalised): timestamp, raw_lat, raw_lon, altitude, speed
    """
    import os
    if os.path.basename(filepath) == "ardupilot_log.csv":
        clean = logparser.build_clean_dataset(filepath)
        # logparser nullifies Longitude (>180) as invalid GPS.
        # Re-read the source XLS to recover the original raw sensor columns
        # (Latitude ~77, Longitude ~405) so _normalise_to_field can remap them.
        src_xls = os.path.join(os.path.dirname(filepath), "drone_flight_with_timestamp.xls")
        raw_src = pd.read_csv(src_xls)
        raw_src.columns = [c.strip().lower() for c in raw_src.columns]
        df = pd.DataFrame({
            "timestamp" : clean["Timestamp"],
            "raw_lat"   : raw_src["latitude"].values,
            "raw_lon"   : raw_src["longitude"].values,
            "altitude"  : clean["Altitude_m"],
            "speed"     : clean["Speed_ms"],
        })
    else:
        fp = filepath.lower()
        if fp.endswith(".csv") or fp.endswith(".xls"):
            try:
                df = pd.read_csv(filepath)
            except Exception:
                df = pd.read_excel(filepath)
        else:
            df = pd.read_excel(filepath)

        df.columns = [c.strip().lower() for c in df.columns]
        rename_map = {
            "timestamp" : "timestamp",
            "latitude"  : "raw_lat",
            "longitude" : "raw_lon",
            "altitude"  : "altitude",
            "speed"     : "speed",
        }
        df = df.rename(columns=rename_map)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def load_and_preprocess(filepath: str) -> pd.DataFrame:
    """
    Load telemetry, attach GPS coordinates, compute timing, and return a
    clean DataFrame ready for grid assignment.

    Columns added:
        lat, lon         — WGS-84 coordinates (mapped if raw values not valid)
        elapsed_s        — seconds since first observation
        is_remapped      — True when coordinates were normalised from raw sensor data
    """
    df = load_raw(filepath)

    if _is_standard_gps(df["raw_lat"], df["raw_lon"]):
        df["lat"] = df["raw_lat"]
        df["lon"] = df["raw_lon"]
        df["is_remapped"] = False
    else:
        df["lat"], df["lon"] = _normalise_to_field(df["raw_lat"], df["raw_lon"])
        df["is_remapped"] = True

    # Time delta from flight start
    t0 = df["timestamp"].iloc[0]
    df["elapsed_s"] = (df["timestamp"] - t0).dt.total_seconds()

    return df


def summarise(df: pd.DataFrame) -> dict:
    """Return a quick statistical summary of the flight."""
    return {
        "n_points"    : len(df),
        "duration_s"  : round(df["elapsed_s"].max(), 2),
        "lat_range"   : (round(df["lat"].min(), 7), round(df["lat"].max(), 7)),
        "lon_range"   : (round(df["lon"].min(), 7), round(df["lon"].max(), 7)),
        "alt_range_m" : (round(df["altitude"].min(), 3), round(df["altitude"].max(), 3)),
        "speed_mps"   : round(df["speed"].mean(), 4),
        "is_remapped" : bool(df["is_remapped"].iloc[0]),
    }


# ─── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    fp = os.path.join(os.path.dirname(__file__), config.INPUT_FILE)
    df = load_and_preprocess(fp)
    print(df[["timestamp", "lat", "lon", "altitude", "elapsed_s"]].head(10).to_string())
    print("\nSummary:", summarise(df))
