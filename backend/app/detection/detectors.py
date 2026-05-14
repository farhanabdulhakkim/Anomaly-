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
    Plug in your ResNet / EfficientNet / YOLOv8 model here.

    Steps to activate:
    1. Set anomaly_mode = "model" on the mission.
    2. Implement _load_model() and _run_inference().
    3. No other file needs to change.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None

    def _load_model(self):
        # Example: self._model = tf.keras.models.load_model(self.model_path)
        raise NotImplementedError("Implement _load_model() with your framework.")

    def _run_inference(self, df: pd.DataFrame) -> np.ndarray:
        # Example: patches = load_image_patches(df)
        #          return (self._model.predict(patches) > 0.5).flatten()
        raise NotImplementedError("Implement _run_inference() with your model.")

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._model is None:
            self._load_model()
        df = df.copy()
        df["anomaly"] = self._run_inference(df).astype(bool)
        return df


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
            model_path = kwargs.get("model_path")
            if not model_path:
                raise ValueError("model_path required for CNN detector")
            return CNNDetector(model_path=model_path)
        raise ValueError(f"Unknown anomaly mode: '{mode}'")
