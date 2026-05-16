"""
detection/detectors.py
======================
Pluggable anomaly detection abstraction.

To add a new model:
1. Subclass BaseAnomalyDetector
2. Implement detect(df) -> pd.DataFrame
3. Register in DetectorFactory
"""

from __future__ import annotations
import abc
from typing import Protocol
import numpy as np
import pandas as pd


# ── Base interface ────────────────────────────────────────────────────────────

class BaseAnomalyDetector(abc.ABC):
    """
    All detectors receive a DataFrame with columns:
        lat, lon, altitude, speed, grid_row, grid_col, elapsed_s
    and must return the same DataFrame with an added boolean `anomaly` column.
    """

    @abc.abstractmethod
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        ...

    def aggregate(self, df: pd.DataFrame) -> dict:
        """Count anomalies per (row, col) cell. Common to all detectors."""
        result = {}
        for (row, col), group in df.groupby(["grid_row", "grid_col"]):
            total = len(group)
            count = int(group["anomaly"].sum())
            result[(int(row), int(col))] = {
                "count": count,
                "total": total,
                "density": round(count / total, 4) if total else 0.0,
            }
        return result


# ── Rule-based detector ───────────────────────────────────────────────────────

class RuleBasedDetector(BaseAnomalyDetector):
    """
    Flags cells where altitude variance exceeds a threshold.
    Proxy for canopy height variation caused by off-type paddy plants.
    """

    def __init__(self, threshold: float = 0.012):
        self.threshold = threshold

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        alt_min, alt_max = df["altitude"].min(), df["altitude"].max()
        df["alt_norm"] = (
            (df["altitude"] - alt_min) / (alt_max - alt_min)
            if alt_max > alt_min else 0.0
        )
        cell_stats = (
            df.groupby(["grid_row", "grid_col"])["alt_norm"]
            .agg(["mean", "std"])
            .rename(columns={"mean": "cell_mean", "std": "cell_std"})
            .fillna(0)
        )
        df = df.join(cell_stats, on=["grid_row", "grid_col"])
        df["anomaly"] = df["cell_std"] > self.threshold
        global_mean = df["alt_norm"].mean()
        global_std  = df["alt_norm"].std()
        df["anomaly"] |= (df["alt_norm"] - global_mean).abs() > 2.0 * global_std
        return df.drop(columns=["alt_norm", "cell_mean", "cell_std"])


# ── Random detector (testing / UI) ────────────────────────────────────────────

class RandomDetector(BaseAnomalyDetector):
    def __init__(self, probability: float = 0.25, seed: int = 42):
        self.probability = probability
        self.seed = seed

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        rng = np.random.default_rng(self.seed)
        df["anomaly"] = rng.random(len(df)) < self.probability
        return df


# ── CNN detector stub ─────────────────────────────────────────────────────────

class CNNDetector(BaseAnomalyDetector):
    """
    CNN-backed detector entry point.

    The extracted PatchCNN works on video frames and is wired through the
    upload-video endpoint. Telemetry-only missions do not contain image
    patches, so this class keeps `anomaly_mode="model"` usable for the
    existing telemetry pipeline by falling back to the altitude-based detector.
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self._telemetry_fallback = RuleBasedDetector()

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        return self._telemetry_fallback.detect(df)


# ── Factory ───────────────────────────────────────────────────────────────────

class DetectorFactory:
    @staticmethod
    def get(mode: str, **kwargs) -> BaseAnomalyDetector:
        if mode == "rule_based":
            return RuleBasedDetector(threshold=kwargs.get("threshold", 0.012))
        if mode == "random":
            return RandomDetector(
                probability=kwargs.get("probability", 0.25),
                seed=kwargs.get("seed", 42),
            )
        if mode == "model":
            return CNNDetector(model_path=kwargs.get("model_path"))
        raise ValueError(f"Unknown anomaly mode: '{mode}'")
