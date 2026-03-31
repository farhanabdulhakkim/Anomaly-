"""
main.py — CLI entry point for the Precision Agriculture Drone Pipeline.

Usage
-----
    python main.py                        # uses INPUT_FILE from config.py
    python main.py path/to/flight.csv     # custom input
    python main.py --mode random          # override anomaly mode
    python main.py --open                 # open map in browser after generation

Pipeline
--------
1. Load & normalise GPS data          (data_processor)
2. Assign 10 m × 10 m grid indices   (grid_engine)
3. Detect / simulate anomalies        (anomaly_simulator)
4. Generate interactive HTML map      (map_generator)
"""

import argparse
import os
import sys
import webbrowser

import config
import data_processor as dp
import grid_engine    as ge
import anomaly_simulator as ams
import map_generator  as mg


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precision Agriculture Drone Anomaly Visualisation Pipeline"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=config.INPUT_FILE,
        help="Path to drone telemetry CSV / XLS (default: %(default)s)",
    )
    parser.add_argument(
        "--mode",
        choices=["random", "rule_based", "model"],
        default=None,
        help="Anomaly detection mode (overrides config.ANOMALY_MODE)",
    )
    parser.add_argument(
        "--output",
        default=config.OUTPUT_HTML,
        help="Output HTML path (default: %(default)s)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated map in the default browser",
    )
    parser.add_argument(
        "--cell-size",
        type=int,
        default=config.CELL_SIZE_M,
        help="Grid cell size in metres (default: %(default)s)",
    )
    return parser.parse_args()


def run_pipeline(input_file: str,
                 anomaly_mode: str | None = None,
                 output_path: str = config.OUTPUT_HTML,
                 cell_size_m: int = config.CELL_SIZE_M) -> str:
    """
    Run the full pipeline and return the path to the generated HTML map.

    This function is also importable for use as a library from Flask or
    other orchestration layers.
    """
    # ── 1. Load ────────────────────────────────────────────────────────────────
    print(f"[1/4] Loading telemetry: {input_file}")
    df = dp.load_and_preprocess(input_file)
    summary_info = dp.summarise(df)
    print(f"      {summary_info['n_points']} points | "
          f"{summary_info['duration_s']}s flight | "
          f"{'coordinate-remapped' if summary_info['is_remapped'] else 'native GPS'}")

    # ── 2. Grid ────────────────────────────────────────────────────────────────
    print(f"[2/4] Assigning {cell_size_m} m × {cell_size_m} m grid indices")
    df = ge.assign_grid_indices(df, cell_m=cell_size_m)
    bbox = ge.field_bounding_box(df, cell_m=cell_size_m)
    print(f"      Grid: {bbox['n_rows']} rows × {bbox['n_cols']} cols "
          f"= {bbox['n_rows'] * bbox['n_cols']} cells")

    # ── 3. Anomaly detection ───────────────────────────────────────────────────
    if anomaly_mode:
        config.ANOMALY_MODE = anomaly_mode
    print(f"[3/4] Running anomaly detection (mode: {config.ANOMALY_MODE})")
    df, anomaly_summary = ams.detect_anomalies(df)
    n_anom_cells  = sum(1 for v in anomaly_summary.values() if v["count"] > 0)
    n_anom_points = int(df["anomaly"].sum())
    print(f"      {n_anom_points} anomalous points in {n_anom_cells} cells")

    # ── 4. Map generation ──────────────────────────────────────────────────────
    print(f"[4/4] Generating Folium map -> {output_path}")
    html_path = mg.generate_map(df, anomaly_summary, output_path=output_path)
    print(f"      Map written: {html_path}")

    return html_path


def main():
    args = parse_args()

    if not os.path.exists(args.input_file):
        print(f"ERROR: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    html_path = run_pipeline(
        input_file   = args.input_file,
        anomaly_mode = args.mode,
        output_path  = args.output,
        cell_size_m  = args.cell_size,
    )

    if args.open:
        print("   Opening map in browser...")
        webbrowser.open(f"file://{html_path}")
    else:
        print(f"\n   Open the map: file://{html_path}")


if __name__ == "__main__":
    main()
