"""
anomaly_simulator.py — Simulate or load anomaly predictions per grid cell.

Three modes are supported (set config.ANOMALY_MODE):

  "random"      — Each point is randomly labelled 0/1 (seeded for reproducibility).
  "rule_based"  — Points with high altitude variance per cell are flagged.
  "model"       — Calls `load_model_predictions()` which you implement to return
                   a {(row, col): count} dict from your CNN inference pipeline.

Aggregation
-----------
Anomalies are *counted per cell*, not just flagged.  The count drives the
colour coding in the Leaflet map (green / amber / orange / red).

Swapping in the real ML model
------------------------------
1.  Set  ANOMALY_MODE = "model"  in config.py.
2.  Implement `load_model_predictions(df)` below — it receives the preprocessed
    DataFrame (with grid_row / grid_col columns) and must return a
    dict { (row, col): anomaly_count }.
3.  No other file needs to change.
"""

import numpy as np
import pandas as pd
from collections import defaultdict

import config


# ─── Mode: random ─────────────────────────────────────────────────────────────

def _random_anomalies(df: pd.DataFrame, seed: int = config.RANDOM_SEED,
                      p: float = config.ANOMALY_PROBABILITY) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = df.copy()
    df["anomaly"] = rng.random(len(df)) < p
    return df


# ─── Mode: rule-based ─────────────────────────────────────────────────────────

def _rule_based_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag a point as anomalous if the altitude reading within its cell
    deviates significantly from the cell's mean altitude.

    Rationale: off-type (taller / shorter) paddy plants create measurable
    canopy-height variation that a drone's altimeter can capture.
    """
    df = df.copy()

    # Normalise altitude across the entire flight (0–1).
    alt_min, alt_max = df["altitude"].min(), df["altitude"].max()
    if alt_max > alt_min:
        df["alt_norm"] = (df["altitude"] - alt_min) / (alt_max - alt_min)
    else:
        df["alt_norm"] = 0.0

    # Per-cell altitude mean and std
    cell_stats = (
        df.groupby(["grid_row", "grid_col"])["alt_norm"]
        .agg(["mean", "std"])
        .rename(columns={"mean": "cell_mean", "std": "cell_std"})
        .fillna(0)
    )
    df = df.join(cell_stats, on=["grid_row", "grid_col"])

    # Flag: normalised altitude std exceeds threshold → anomaly
    threshold = config.ALTITUDE_ANOMALY_THRESHOLD
    df["anomaly"] = df["cell_std"] > threshold

    # Secondary rule: altitude reading is an outlier vs the global flight average
    # (catches single-point spikes that don't raise cell std but still deviate).
    global_alt_mean = df["alt_norm"].mean()
    global_alt_std  = df["alt_norm"].std()
    df["anomaly"] |= (df["alt_norm"] - global_alt_mean).abs() > 2.0 * global_alt_std

    df = df.drop(columns=["alt_norm", "cell_mean", "cell_std"])
    return df


# ─── Mode: model (stub) ───────────────────────────────────────────────────────

def load_model_predictions(df: pd.DataFrame) -> dict:
    """
    STUB — Replace this with your CNN inference pipeline.

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed telemetry with grid_row / grid_col columns.

    Returns
    -------
    dict
        { (row, col): anomaly_count }  — one entry per grid cell.

    Example implementation:
        model = tf.keras.models.load_model("cnn_paddy_v1.h5")
        patches = load_image_patches(df)           # your image loading logic
        preds   = (model.predict(patches) > 0.5)   # binary classification
        result  = defaultdict(int)
        for i, row in df.iterrows():
            if preds[i]:
                result[(row["grid_row"], row["grid_col"])] += 1
        return dict(result)
    """
    raise NotImplementedError(
        "Replace load_model_predictions() with your CNN inference code."
    )


# ─── Aggregation ──────────────────────────────────────────────────────────────

def aggregate_anomalies(df: pd.DataFrame) -> dict:
    """
    Count anomalies per grid cell.

    Returns
    -------
    dict
        { (row, col): {"count": int, "total": int, "density": float} }
    """
    result = {}
    for (row, col), group in df.groupby(["grid_row", "grid_col"]):
        total  = len(group)
        count  = int(group["anomaly"].sum())
        result[(int(row), int(col))] = {
            "count"  : count,
            "total"  : total,
            "density": round(count / total, 4) if total else 0.0,
        }
    return result


# ─── Main entry point ─────────────────────────────────────────────────────────

def detect_anomalies(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Run anomaly detection in the mode specified by config.ANOMALY_MODE.

    Returns
    -------
    df      : DataFrame with an `anomaly` boolean column added.
    summary : dict { (row, col): {count, total, density} }
    """
    mode = config.ANOMALY_MODE.lower()

    if mode == "random":
        df = _random_anomalies(df)
    elif mode == "rule_based":
        df = _rule_based_anomalies(df)
    elif mode == "model":
        cell_counts = load_model_predictions(df)   # returns {(r,c): count}
        df["anomaly"] = False
        for (r, c), cnt in cell_counts.items():
            mask = (df["grid_row"] == r) & (df["grid_col"] == c)
            if cnt > 0:
                # Flag the first `cnt` points in the cell as anomalous
                idx = df[mask].index[:cnt]
                df.loc[idx, "anomaly"] = True
    else:
        raise ValueError(f"Unknown ANOMALY_MODE: '{mode}'. "
                         "Choose 'random', 'rule_based', or 'model'.")

    summary = aggregate_anomalies(df)
    return df, summary


# ─── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_processor import load_and_preprocess
    from grid_engine import assign_grid_indices

    fp  = os.path.join(os.path.dirname(__file__), config.INPUT_FILE)
    df  = load_and_preprocess(fp)
    df  = assign_grid_indices(df)
    df, summary = detect_anomalies(df)

    anomaly_cells = {k: v for k, v in summary.items() if v["count"] > 0}
    print(f"Mode           : {config.ANOMALY_MODE}")
    print(f"Total points   : {len(df)}")
    print(f"Anomalous pts  : {df['anomaly'].sum()}")
    print(f"Cells visited  : {len(summary)}")
    print(f"Anomaly cells  : {len(anomaly_cells)}")
    for k, v in list(anomaly_cells.items())[:5]:
        print(f"  Cell {k}: {v}")
