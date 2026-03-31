"""
map_generator.py — Build an interactive Folium map from processed drone data.

Layers
------
1. Grid overlay   — colour-coded rectangles per 10 m × 10 m cell
2. Flight path    — PolyLine with start / end markers
3. Anomaly points — CircleMarkers at flagged GPS positions
"""

import os
import folium
from folium.plugins import AntPath
import pandas as pd

import config
from grid_engine import build_grid_cells, field_bounding_box


# ─── Colour helper ────────────────────────────────────────────────────────────

def _cell_color(count: int) -> str:
    if count == 0:  return config.COLOR_NORMAL
    if count == 1:  return config.COLOR_LOW
    if count == 2:  return config.COLOR_MED
    return config.COLOR_HIGH


# ─── Layer builders ───────────────────────────────────────────────────────────

def _add_grid(m: folium.Map, df: pd.DataFrame, summary: dict) -> None:
    cells = build_grid_cells(df)
    layer = folium.FeatureGroup(name="Grid overlay", show=True)
    for _, cell in cells.iterrows():
        key   = (int(cell["row"]), int(cell["col"]))
        info  = summary.get(key, {"count": 0, "total": 0, "density": 0.0})
        color = _cell_color(info["count"])
        popup = (
            f"<b>Cell [{key[0]}, {key[1]}]</b><br>"
            f"Anomalies: {info['count']} / {info['total']}<br>"
            f"Density: {info['density']*100:.1f}%"
        )
        folium.Rectangle(
            bounds=[[cell["sw_lat"], cell["sw_lon"]],
                    [cell["ne_lat"], cell["ne_lon"]]],
            color="#ffffff",
            weight=0.8,
            fill=True,
            fill_color=color,
            fill_opacity=0.55 if info["count"] > 0 else 0.18,
            popup=folium.Popup(popup, max_width=200),
            tooltip=f"Row {key[0]}, Col {key[1]} — {info['count']} anomaly/ies",
        ).add_to(layer)
    layer.add_to(m)


def _add_flight_path(m: folium.Map, df: pd.DataFrame) -> None:
    coords = list(zip(df["lat"], df["lon"]))
    layer  = folium.FeatureGroup(name="Drone flight path", show=True)

    # Animated dashed path
    AntPath(
        locations=coords,
        color="#60a5fa",
        weight=2.5,
        opacity=0.85,
        delay=800,
        dash_array=[10, 20],
    ).add_to(layer)

    # Start marker
    folium.CircleMarker(
        coords[0], radius=7, color="#22c55e", fill=True,
        fill_color="#22c55e", fill_opacity=1,
        tooltip="Flight Start",
    ).add_to(layer)

    # End marker
    folium.CircleMarker(
        coords[-1], radius=7, color="#f59e0b", fill=True,
        fill_color="#f59e0b", fill_opacity=1,
        tooltip="Flight End",
    ).add_to(layer)

    layer.add_to(m)


def _add_anomaly_points(m: folium.Map, df: pd.DataFrame) -> None:
    anom  = df[df["anomaly"] == True]
    layer = folium.FeatureGroup(name="Anomaly points", show=True)
    for _, row in anom.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            color="#dc2626",
            fill=True,
            fill_color="#ef4444",
            fill_opacity=0.9,
            popup=folium.Popup(
                f"<b>⚠️ Anomaly</b><br>"
                f"Cell: [{int(row['grid_row'])}, {int(row['grid_col'])}]<br>"
                f"Altitude: {row['altitude']:.2f} m<br>"
                f"Time: +{row['elapsed_s']:.1f} s",
                max_width=180,
            ),
        ).add_to(layer)
    layer.add_to(m)


def _add_legend(m: folium.Map, summary: dict) -> None:
    anomaly_cells = sum(1 for v in summary.values() if v["count"] > 0)
    clean_cells   = len(summary) - anomaly_cells
    legend_html = f"""
    <div style="position:fixed;bottom:30px;left:30px;z-index:9999;
                background:#1f2937;border:1px solid #374151;border-radius:10px;
                padding:14px 16px;font-family:sans-serif;color:#e2e8f0;
                font-size:13px;min-width:200px;box-shadow:0 4px 12px rgba(0,0,0,.5)">
      <b style="font-size:14px">🌾 Anomaly Legend</b><br><br>
      <span style="background:{config.COLOR_NORMAL};display:inline-block;
            width:14px;height:14px;border-radius:3px;margin-right:6px"></span>No anomaly<br>
      <span style="background:{config.COLOR_LOW};display:inline-block;
            width:14px;height:14px;border-radius:3px;margin-right:6px"></span>Low (1 detection)<br>
      <span style="background:{config.COLOR_MED};display:inline-block;
            width:14px;height:14px;border-radius:3px;margin-right:6px"></span>Medium (2 detections)<br>
      <span style="background:{config.COLOR_HIGH};display:inline-block;
            width:14px;height:14px;border-radius:3px;margin-right:6px"></span>High (≥3 detections)<br>
      <hr style="border-color:#374151;margin:8px 0">
      <b>Mode:</b> {config.ANOMALY_MODE.replace('_',' ').title()}<br>
      <b>Anomaly cells:</b> <span style="color:#f87171">{anomaly_cells}</span><br>
      <b>Clean cells:</b> <span style="color:#4ade80">{clean_cells}</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_map(
    df: pd.DataFrame,
    summary: dict,
    output_path: str = config.OUTPUT_HTML,
) -> str:
    """
    Build a Folium map with grid, flight path, and anomaly layers.

    Parameters
    ----------
    df          : Preprocessed DataFrame with lat/lon, grid indices, anomaly flag.
    summary     : { (row, col): {count, total, density} } from anomaly_simulator.
    output_path : File path for the output HTML.

    Returns
    -------
    str — Absolute path to the written HTML file.
    """
    bbox   = field_bounding_box(df)
    centre = (
        (bbox["sw"][0] + bbox["ne"][0]) / 2,
        (bbox["sw"][1] + bbox["ne"][1]) / 2,
    )

    m = folium.Map(
        location=centre,
        zoom_start=config.MAP_ZOOM,
        tiles=config.TILE_URL,
        attr=config.TILE_ATTRIB,
    )

    _add_grid(m, df, summary)
    _add_flight_path(m, df)
    _add_anomaly_points(m, df)
    _add_legend(m, summary)

    folium.LayerControl(collapsed=False).add_to(m)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    m.save(output_path)
    return os.path.abspath(output_path)
