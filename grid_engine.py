"""
grid_engine.py — Convert GPS points to a 10 m × 10 m grid and build field geometry.

Design
------
• The field origin (0, 0) is placed at the south-west corner of the bounding box.
• Grid indices (row, col) increase northward and eastward respectively.
• Haversine is used for *accuracy checks*; the primary conversion uses a fast
  equirectangular approximation that is accurate to <0.1 % over areas < 5 km².
• All cell geometry (corner coordinates) is returned in WGS-84 so Leaflet can
  render it directly without any further projection.

Extensibility
-------------
Swap `assign_grid_indices` with a pyproj-based UTM transformer for metre-perfect
accuracy over large fields:

    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
    east, north = t.transform(lon_arr, lat_arr)
    col = ((east  - east_origin)  / cell_m).astype(int)
    row = ((north - north_origin) / cell_m).astype(int)
"""

import math
import numpy as np
import pandas as pd

import config


# ─── Haversine (for reference / validation) ────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000  # Earth radius (m)
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ─── Equirectangular projection helpers ────────────────────────────────────────

def latlon_to_metres(lat: float, lon: float,
                     origin_lat: float, origin_lon: float) -> tuple[float, float]:
    """
    Convert (lat, lon) to (north_m, east_m) relative to an origin point.
    Fast equirectangular approximation; < 0.1 % error within 5 km of origin.
    """
    north_m = (lat - origin_lat) * config.METRES_PER_DEG_LAT
    east_m  = (lon - origin_lon) * config.METRES_PER_DEG_LON
    return north_m, east_m


def metres_to_latlon(north_m: float, east_m: float,
                     origin_lat: float, origin_lon: float) -> tuple[float, float]:
    """Inverse of `latlon_to_metres`."""
    lat = origin_lat + north_m / config.METRES_PER_DEG_LAT
    lon = origin_lon + east_m  / config.METRES_PER_DEG_LON
    return lat, lon


# ─── Grid assignment ───────────────────────────────────────────────────────────

def assign_grid_indices(df: pd.DataFrame,
                        cell_m: int = config.CELL_SIZE_M) -> pd.DataFrame:
    """
    Add `grid_row` and `grid_col` columns to *df*.

    The field origin is the south-west corner (min lat, min lon) of the
    observed flight extent, padded by half a cell on each side so that
    boundary points land inside the grid, not on its edge.
    """
    origin_lat = df["lat"].min() - (cell_m / config.METRES_PER_DEG_LAT) / 2
    origin_lon = df["lon"].min() - (cell_m / config.METRES_PER_DEG_LON) / 2

    north_m = (df["lat"] - origin_lat) * config.METRES_PER_DEG_LAT
    east_m  = (df["lon"] - origin_lon) * config.METRES_PER_DEG_LON

    df = df.copy()
    df["grid_row"]   = (north_m / cell_m).astype(int)
    df["grid_col"]   = (east_m  / cell_m).astype(int)
    df["origin_lat"] = origin_lat
    df["origin_lon"] = origin_lon
    df["cell_m"]     = cell_m
    return df


# ─── Cell geometry ─────────────────────────────────────────────────────────────

def build_grid_cells(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame of unique grid cells with their four corner coordinates.

    Columns: row, col, sw_lat, sw_lon, ne_lat, ne_lon, centre_lat, centre_lon
    """
    origin_lat = df["origin_lat"].iloc[0]
    origin_lon = df["origin_lon"].iloc[0]
    cell_m     = df["cell_m"].iloc[0]

    cells = df[["grid_row", "grid_col"]].drop_duplicates().copy()
    cells.columns = ["row", "col"]

    # South-West corner of each cell
    cells["sw_lat"] = origin_lat + cells["row"] * cell_m / config.METRES_PER_DEG_LAT
    cells["sw_lon"] = origin_lon + cells["col"] * cell_m / config.METRES_PER_DEG_LON

    # North-East corner
    cells["ne_lat"] = cells["sw_lat"] + cell_m / config.METRES_PER_DEG_LAT
    cells["ne_lon"] = cells["sw_lon"] + cell_m / config.METRES_PER_DEG_LON

    # Centre
    cells["centre_lat"] = (cells["sw_lat"] + cells["ne_lat"]) / 2
    cells["centre_lon"] = (cells["sw_lon"] + cells["ne_lon"]) / 2

    return cells.reset_index(drop=True)


def field_bounding_box(df: pd.DataFrame, cell_m: int = config.CELL_SIZE_M) -> dict:
    """
    Return the WGS-84 bounding box of the entire grid (useful for map fitting).

    Returns: {"sw": (lat, lon), "ne": (lat, lon), "n_rows": int, "n_cols": int}
    """
    origin_lat = df["origin_lat"].iloc[0]
    origin_lon = df["origin_lon"].iloc[0]
    n_rows = df["grid_row"].max() + 1
    n_cols = df["grid_col"].max() + 1

    ne_lat = origin_lat + n_rows * cell_m / config.METRES_PER_DEG_LAT
    ne_lon = origin_lon + n_cols * cell_m / config.METRES_PER_DEG_LON

    return {
        "sw"    : (round(origin_lat, 7), round(origin_lon, 7)),
        "ne"    : (round(ne_lat, 7),     round(ne_lon, 7)),
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
    }


# ─── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_processor import load_and_preprocess

    fp = os.path.join(os.path.dirname(__file__), config.INPUT_FILE)
    df = load_and_preprocess(fp)
    df = assign_grid_indices(df)

    cells = build_grid_cells(df)
    bbox  = field_bounding_box(df)

    print(f"Grid: {bbox['n_rows']} rows × {bbox['n_cols']} cols "
          f"= {bbox['n_rows'] * bbox['n_cols']} cells")
    print(f"Bounding box SW: {bbox['sw']}  NE: {bbox['ne']}")
    print(cells.head(5).to_string())
