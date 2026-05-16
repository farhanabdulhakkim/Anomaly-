from __future__ import annotations

import math
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import matplotlib
import numpy as np
import pandas as pd
import torch

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from model import PATCH_SIZE, STRIDE, PatchCNN


HYBRID_RATIO_THRESHOLD = 0.01
CONF_THRESHOLD = 0.55
BATCH_SIZE = 512
CELL_SIZE_M = 10


@dataclass
class VideoAnomaly:
    lat: float
    lng: float
    grid_row: int
    grid_col: int
    frame_index: int
    ratio: float
    confidence: float


@dataclass
class VideoDetectionResult:
    anomalies: list[VideoAnomaly]
    grid_path: Path
    frames_processed: int
    frames_extracted: int


def run_video_cnn_detection(
    video_path: str | Path,
    gps_log_path: str | Path,
    output_grid_path: str | Path,
    *,
    work_dir: str | Path,
    model_path: str | Path | None = None,
    cmd_bounds: str | None = None,
) -> VideoDetectionResult:
    """Run the extracted PatchCNN video pipeline without shelling out."""
    video_path = Path(video_path)
    gps_log_path = Path(gps_log_path)
    output_grid_path = Path(output_grid_path)
    work_dir = Path(work_dir)
    frames_dir = work_dir / "frames"
    overlays_dir = work_dir / "overlays"
    anomaly_frames_dir = work_dir / "anomaly_frames"
    for path in (frames_dir, overlays_dir, anomaly_frames_dir, output_grid_path.parent):
        path.mkdir(parents=True, exist_ok=True)

    frames, timestamps, extracted_count, fps = _extract_detection_frames(video_path, frames_dir)
    gps_data = _read_gps_log(gps_log_path)
    if gps_data.empty:
        raise ValueError("No usable GPS rows found in uploaded CSV")

    grid_info = _build_grid(gps_data, cmd_bounds)
    model = _load_model(model_path)

    frame_results = _detect_anomaly_frames(
        frames=frames,
        model=model,
        overlays_dir=overlays_dir,
        anomaly_frames_dir=anomaly_frames_dir,
    )
    anomalies, grid = _map_frames_to_grid(frame_results, timestamps, gps_data, grid_info)
    _save_grid_image(grid, output_grid_path)

    return VideoDetectionResult(
        anomalies=anomalies,
        grid_path=output_grid_path,
        frames_processed=len(frames),
        frames_extracted=extracted_count,
    )


def bounds_from_waypoints(waypoints: Iterable[dict] | None) -> str | None:
    if not waypoints:
        return None
    lats = [float(w["lat"]) for w in waypoints if w.get("lat") is not None]
    lons = [float(w.get("lon", w.get("lng"))) for w in waypoints if w.get("lon", w.get("lng")) is not None]
    if not lats or not lons:
        return None
    return f"{min(lats)},{max(lats)},{min(lons)},{max(lons)}"


def _extract_detection_frames(video_path: Path, frames_dir: Path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
    frame_interval = max(1, int(fps))
    frames: list[np.ndarray] = []
    timestamps: list[float] = []
    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imwrite(str(frames_dir / f"frame_{count}.jpg"), frame)
        if count % frame_interval == 0:
            frames.append(frame)
            timestamps.append(count / fps)
        count += 1

    cap.release()
    if not frames:
        raise ValueError("No frames could be extracted from uploaded video")
    return frames, timestamps, count, fps


def _read_gps_log(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, on_bad_lines="skip", engine="python")
    lower = {str(c).strip().lower(): c for c in df.columns}

    if {"time", "lat", "lon"}.issubset(lower):
        out = pd.DataFrame(
            {
                "time": pd.to_datetime(df[lower["time"]], errors="coerce"),
                "lat": pd.to_numeric(df[lower["lat"]], errors="coerce"),
                "lon": pd.to_numeric(df[lower["lon"]], errors="coerce"),
            }
        )
        return out.dropna().sort_values("time").reset_index(drop=True)

    if {"timestamp", "latitude", "longitude"}.issubset(lower):
        out = pd.DataFrame(
            {
                "time": pd.to_datetime(df[lower["timestamp"]], errors="coerce"),
                "lat": pd.to_numeric(df[lower["latitude"]], errors="coerce"),
                "lon": pd.to_numeric(df[lower["longitude"]], errors="coerce"),
            }
        )
        return out.dropna().sort_values("time").reset_index(drop=True)

    from final_log import parse_log

    pos_df, gps_df, _ = parse_log(str(path))
    source = gps_df if not gps_df.empty else pos_df.rename(columns={"lng": "lon"})
    lng_col = "lng" if "lng" in source.columns else "lon"
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(source["ts"], errors="coerce"),
            "lat": pd.to_numeric(source["lat"], errors="coerce"),
            "lon": pd.to_numeric(source[lng_col], errors="coerce"),
        }
    )
    return out.dropna().sort_values("time").reset_index(drop=True)


def _build_grid(gps_data: pd.DataFrame, cmd_bounds: str | None):
    min_lat, max_lat = gps_data["lat"].min(), gps_data["lat"].max()
    min_lon, max_lon = gps_data["lon"].min(), gps_data["lon"].max()

    if cmd_bounds:
        parts = [float(v) for v in cmd_bounds.split(",")]
        grid_min_lat, grid_max_lat = parts[0], parts[1]
        grid_min_lon, grid_max_lon = parts[2], parts[3]
    else:
        grid_min_lat, grid_max_lat = min_lat, max_lat
        grid_min_lon, grid_max_lon = min_lon, max_lon

    avg_grid_lat = (grid_min_lat + grid_max_lat) / 2
    cell_lat = CELL_SIZE_M / 111000
    cell_lon = CELL_SIZE_M / (111000 * np.cos(np.radians(avg_grid_lat)))
    grid_rows = max(1, math.ceil((grid_max_lat - grid_min_lat) / cell_lat))
    grid_cols = max(1, math.ceil((grid_max_lon - grid_min_lon) / cell_lon))
    return {
        "min_lat": grid_min_lat,
        "min_lon": grid_min_lon,
        "cell_lat": cell_lat,
        "cell_lon": cell_lon,
        "rows": grid_rows,
        "cols": grid_cols,
    }


def _load_model(model_path: str | Path | None = None):
    if model_path is None:
        model_path = Path(__file__).resolve().parents[2] / "patch_cnn_model.pth"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = PatchCNN().to(device)
    model.load_state_dict(torch.load(str(model_path), map_location=device))
    model.eval()
    return model


def _detect_anomaly_frames(frames, model, overlays_dir: Path, anomaly_frames_dir: Path):
    device = next(model.parameters()).device
    results = []

    for frame_index, frame in enumerate(frames):
        h, w = frame.shape[:2]
        pred_mask = np.zeros((h, w), dtype=np.uint8)
        patches, positions = [], []

        for y in range(0, h - PATCH_SIZE + 1, STRIDE):
            for x in range(0, w - PATCH_SIZE + 1, STRIDE):
                patch = frame[y : y + PATCH_SIZE, x : x + PATCH_SIZE]
                patch = (patch / 255.0).astype(np.float32)
                patches.append(np.transpose(patch, (2, 0, 1)))
                positions.append((x, y))

        if not patches:
            results.append({"is_anomaly": False, "ratio": 0.0, "confidence": 0.0})
            continue

        hybrid_patch_count = 0
        max_confidence = 0.0
        all_preds, all_confs = [], []

        for start in range(0, len(patches), BATCH_SIZE):
            batch_tensor = torch.tensor(np.stack(patches[start : start + BATCH_SIZE])).to(device)
            with torch.no_grad():
                logits = model(batch_tensor)
                preds = logits.argmax(1).cpu().numpy()
                confs = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
            all_preds.extend(preds)
            all_confs.extend(confs)

        for (x, y), pred, conf in zip(positions, all_preds, all_confs):
            max_confidence = max(max_confidence, float(conf))
            if pred == 1:
                hybrid_patch_count += 1
                cv2.circle(pred_mask, (x + PATCH_SIZE // 2, y + PATCH_SIZE // 2), 2, 1, -1)

        ratio = hybrid_patch_count / len(patches)
        is_anomaly = ratio > HYBRID_RATIO_THRESHOLD or max_confidence > CONF_THRESHOLD

        overlay = frame.copy()
        overlay[pred_mask == 1] = [0, 0, 255]
        blended = cv2.addWeighted(frame, 0.7, overlay, 0.4, 0)
        cv2.imwrite(str(overlays_dir / f"frame{frame_index}_cnn.png"), blended)

        if is_anomaly:
            annotated = blended.copy()
            cv2.putText(annotated, "Anomaly", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            cv2.rectangle(annotated, (5, 5), (w - 5, h - 5), (0, 0, 255), 3)
            cv2.imwrite(str(anomaly_frames_dir / f"anomaly_frame_{frame_index}.jpg"), annotated)

        results.append({"is_anomaly": is_anomaly, "ratio": ratio, "confidence": max_confidence})

    return results


def _map_frames_to_grid(frame_results, timestamps, gps_data: pd.DataFrame, grid_info: dict):
    grid = np.zeros((grid_info["rows"], grid_info["cols"]))
    gps_start = gps_data["time"].iloc[0]
    gps_times = (gps_data["time"] - gps_start).dt.total_seconds().to_numpy()
    gps_lats = gps_data["lat"].to_numpy()
    gps_lons = gps_data["lon"].to_numpy()
    anomalies: list[VideoAnomaly] = []

    gps_lat_spread = (gps_lats.max() - gps_lats.min()) * 111000
    gps_lon_spread = (gps_lons.max() - gps_lons.min()) * 111000 * np.cos(np.radians(np.mean(gps_lats)))
    use_distributed = max(gps_lat_spread, gps_lon_spread) < 5.0

    for frame_index, frame_time in enumerate(timestamps):
        if use_distributed:
            idx = int(frame_index / max(len(timestamps) - 1, 1) * (len(gps_data) - 1))
            lat = float(gps_lats[idx])
            lon = float(gps_lons[idx])
        else:
            t = float(np.clip(frame_time, gps_times[0], gps_times[-1]))
            lat = float(np.interp(t, gps_times, gps_lats))
            lon = float(np.interp(t, gps_times, gps_lons))

        row = int((lat - grid_info["min_lat"]) / grid_info["cell_lat"])
        col = int((lon - grid_info["min_lon"]) / grid_info["cell_lon"])
        row = int(np.clip(row, 0, grid_info["rows"] - 1))
        col = int(np.clip(col, 0, grid_info["cols"] - 1))

        result = frame_results[frame_index]
        if result["is_anomaly"]:
            grid[row, col] += 1
            anomalies.append(
                VideoAnomaly(
                    lat=lat,
                    lng=lon,
                    grid_row=row,
                    grid_col=col,
                    frame_index=frame_index,
                    ratio=result["ratio"],
                    confidence=result["confidence"],
                )
            )

    return anomalies, grid


def _save_grid_image(grid: np.ndarray, output_grid_path: Path) -> None:
    plt.figure(figsize=(8, 6))
    plt.imshow(grid, cmap="Reds", origin="lower")
    plt.colorbar(label="Anomaly Count")

    letters = list(string.ascii_uppercase)
    for row in range(grid.shape[0]):
        for col in range(grid.shape[1]):
            label = f"{letters[col] if col < len(letters) else col + 1}{row + 1}\n{int(grid[row, col])}"
            plt.text(col, row, label, ha="center", va="center", color="black", fontsize=9, fontweight="bold")

    plt.title("Anomaly Grid Map (Labeled)")
    plt.xlabel("Longitude Cells")
    plt.ylabel("Latitude Cells")
    plt.grid(True)
    plt.savefig(output_grid_path)
    plt.close()
