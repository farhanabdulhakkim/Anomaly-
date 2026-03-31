"""
app.py — Optional Flask back-end for serving the drone anomaly map.

Endpoints
---------
GET  /                      → Serve the generated HTML map
GET  /api/status            → Pipeline health-check
GET  /api/anomalies         → JSON list of anomalous grid cells
GET  /api/grid              → Full grid cell GeoJSON
POST /api/run               → Re-run the pipeline with optional params
POST /api/upload            → Upload a new telemetry file and re-run

Run
---
    python app.py
    # or:
    FLASK_APP=app.py flask run --host=0.0.0.0 --port=5000
"""

import json
import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

import config
from main import run_pipeline
import data_processor as dp
import grid_engine    as ge
import anomaly_simulator as ams

app = Flask(__name__)

# Keep the latest pipeline state in memory for API queries.
_state: dict = {}


def _refresh_state(input_file: str = config.INPUT_FILE,
                   anomaly_mode: str | None = None) -> None:
    global _state

    df = dp.load_and_preprocess(input_file)
    df = ge.assign_grid_indices(df)
    df, summary = ams.detect_anomalies(df)

    _state = {
        "df"     : df,
        "summary": summary,
        "bbox"   : ge.field_bounding_box(df),
        "mode"   : config.ANOMALY_MODE,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the pre-generated HTML map."""
    html = Path(config.OUTPUT_HTML)
    if not html.exists():
        run_pipeline(config.INPUT_FILE)
    return send_file(str(html.resolve()))


@app.route("/api/status")
def status():
    return jsonify({
        "status"    : "ok",
        "map_ready" : Path(config.OUTPUT_HTML).exists(),
        "mode"      : config.ANOMALY_MODE,
        "input_file": config.INPUT_FILE,
    })


@app.route("/api/anomalies")
def anomalies():
    """Return anomalous grid cells as a JSON list."""
    if not _state:
        _refresh_state()
    result = [
        {"row": k[0], "col": k[1], **v}
        for k, v in _state["summary"].items()
        if v["count"] > 0
    ]
    result.sort(key=lambda x: x["count"], reverse=True)
    return jsonify({
        "anomaly_cells": result,
        "total_anomaly_cells": len(result),
        "mode": _state["mode"],
        "bbox": _state["bbox"],
    })


@app.route("/api/grid")
def grid():
    """Return all grid cells with anomaly metadata (GeoJSON)."""
    if not _state:
        _refresh_state()
    df      = _state["df"]
    summary = _state["summary"]

    from map_generator import _grid_cells_geojson
    geojson = _grid_cells_geojson(df, summary)
    return app.response_class(
        response=json.dumps(geojson),
        status=200,
        mimetype="application/json",
    )


@app.route("/api/run", methods=["POST"])
def rerun():
    """
    Re-run the pipeline.  Optional JSON body:
        { "mode": "random" | "rule_based", "cell_size": 10 }
    """
    body      = request.get_json(silent=True) or {}
    mode      = body.get("mode", config.ANOMALY_MODE)
    cell_size = int(body.get("cell_size", config.CELL_SIZE_M))

    html_path = run_pipeline(
        input_file   = config.INPUT_FILE,
        anomaly_mode = mode,
        cell_size_m  = cell_size,
    )
    _refresh_state(anomaly_mode=mode)
    return jsonify({"status": "ok", "map": html_path, "mode": mode})


@app.route("/api/upload", methods=["POST"])
def upload():
    """
    Accept a telemetry file upload, run the pipeline on it, and return
    the updated map URL.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No selected file"}), 400

    suffix = Path(f.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        html_path = run_pipeline(input_file=tmp_path)
        _refresh_state(input_file=tmp_path)
        return jsonify({"status": "ok", "map": html_path})
    finally:
        os.unlink(tmp_path)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pre-generate the map on startup
    if not Path(config.OUTPUT_HTML).exists():
        print("Pre-generating map …")
        run_pipeline(config.INPUT_FILE)
    _refresh_state()

    app.run(
        host  = config.FLASK_HOST,
        port  = config.FLASK_PORT,
        debug = config.FLASK_DEBUG,
    )
